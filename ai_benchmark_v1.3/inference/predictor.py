import json
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from tqdm import tqdm

from ai_benchmark.config import BenchmarkConfig
from ai_benchmark.models.base import ModelProvider
from ai_benchmark.schemas import PredictionRecord, BenchmarkSummary
from ai_benchmark.evaluation.normalization import deterministic_normalize_prediction


class BenchmarkPredictor:
    """
    Điều phối quy trình inference trên tập dataset:
    - Hỗ trợ limit, sampling, stratified sampling
    - Streaming JSONL persistence (lưu ngay lập tức sau từng mẫu)
    - Resume mechanism (bỏ qua mẫu đã có kết quả dự đoán)
    - Đo đạc chi tiết latency, throughput, token usage, GPU memory
    """

    def __init__(
        self,
        model_provider: ModelProvider,
        predictions_file: Optional[str | Path] = None,
        dataset_path: Optional[str | Path] = None,
        mode: Optional[str] = None,
        use_rag: bool = False,
        rag_top_k: int = BenchmarkConfig.RAG_TOP_K,
        rag_threshold: float = BenchmarkConfig.RAG_THRESHOLD,
        force: bool = False
    ):
        self.model_provider = model_provider
        self.dataset_path = Path(dataset_path or BenchmarkConfig.DEFAULT_DATASET_PATH)
        
        # Đồng bộ mode và use_rag (backward compatibility)
        if mode in ("no-rag", "legacy-rag", "normalization-rag"):
            self.mode = mode
        elif use_rag:
            self.mode = "legacy-rag"
        else:
            self.mode = "no-rag"


        self.use_rag = (self.mode == "legacy-rag")
        self.rag_top_k = rag_top_k
        self.rag_threshold = rag_threshold
        self.rag_service = None
        self.normalizer = None
        self.force = force

        if self.mode == "normalization-rag":
            try:
                try:
                    from app.ai.rag.normalization_service import NormalizationService
                except ImportError:
                    try:
                        from ai_benchmark.rag.normalization_service import NormalizationService
                    except ImportError:
                        from rag.normalization_service import NormalizationService
                print("[*] Đang khởi tạo Normalization RAG Service...")
                self.normalizer = NormalizationService()
                print("[✓] Khởi tạo Normalization RAG Service thành công.")
            except Exception as e:
                print(f"[!] Không thể khởi tạo Normalization RAG ({e}). Sẽ chạy no-rag.")
                self.mode = "no-rag"

        elif self.mode == "legacy-rag":
            try:
                try:
                    from app.ai.rag.rag_service import RAGService
                    from app.ai.rag.vector_store import VectorStore
                except ImportError:
                    try:
                        from ai_benchmark.rag.rag_service import RAGService
                        from ai_benchmark.rag.vector_store import VectorStore
                    except ImportError:
                        from rag.rag_service import RAGService
                        from rag.vector_store import VectorStore
                print("[*] Đang khởi tạo Legacy RAG Service & VectorStore...")
                vs = VectorStore(
                    knowledge_path=str(BenchmarkConfig.RAG_KNOWLEDGE_PATH),
                    persist_path=str(BenchmarkConfig.RAG_CHROMA_PATH)
                )
                self.rag_service = RAGService(vector_store=vs)
                print("[✓] Khởi tạo Legacy RAG Service thành công.")
            except Exception as e:
                print(f"[!] Không thể khởi tạo RAG ({e}). Sẽ chạy benchmark không có RAG.")
                self.mode = "no-rag"
                self.use_rag = False


        # Đặt tên file prediction theo tên model và mode nếu không được chỉ định
        if predictions_file:
            self.predictions_file = Path(predictions_file)
        else:
            import re
            safe_name = re.sub(r"[^a-zA-Z0-9_\.]", "_", model_provider.model_name)
            if self.mode == "normalization-rag":
                mode_suffix = "_normalization_rag"
            elif self.mode == "legacy-rag":
                mode_suffix = "_rag"
            else:
                mode_suffix = ""
            self.predictions_file = BenchmarkConfig.PREDICTIONS_DIR / f"{safe_name}{mode_suffix}_predictions.jsonl"


        self.predictions_file.parent.mkdir(parents=True, exist_ok=True)

        # Nếu có cờ force -> xóa file cũ để chạy lại từ đầu
        if self.force and self.predictions_file.exists():
            self.predictions_file.unlink()
            print(f"[*] Cờ --force được bật: Đã làm mới file {self.predictions_file.name}")

    def load_dataset(
        self,
        limit: Optional[int] = None,
        sample: Optional[int] = None,
        stratified: bool = False,
        random_state: int = 42
    ) -> pd.DataFrame:
        """Đọc dataset từ file CSV kèm các chế độ lọc/sample/stratified."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file dataset: {self.dataset_path}")

        df = pd.read_csv(self.dataset_path)

        if stratified and sample and sample < len(df) and "intent" in df.columns:
            # Stratified sampling dựa trên intent
            try:
                frac = sample / len(df)
                df = df.groupby("intent", group_keys=False).apply(
                    lambda x: x.sample(frac=frac, random_state=random_state)
                )
                df = df.head(sample)
            except Exception as e:
                print(f"[Warning] Lỗi stratified sampling ({e}). Chuyển sang sample ngẫu nhiên.")
                df = df.sample(n=sample, random_state=random_state)
        elif sample and sample < len(df):
            df = df.sample(n=sample, random_state=random_state)
        elif limit and limit > 0:
            df = df.head(limit)

        return df

    def get_existing_completed_ids(self) -> set:
        """Đọc các sample ID đã có trong file jsonl để phục vụ Resume."""
        completed_ids = set()
        if self.predictions_file.exists():
            with open(self.predictions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        completed_ids.add(str(record["id"]))
                    except Exception:
                        pass
        return completed_ids

    def run(
        self,
        limit: Optional[int] = None,
        sample: Optional[int] = None,
        stratified: bool = False,
        delay_seconds: float = 0.0
    ) -> Dict[str, Any]:
        """
        Thực thi toàn bộ tiến trình benchmark inference.
        Ghi dữ liệu streaming vào file JSONL.
        """
        df = self.load_dataset(limit=limit, sample=sample, stratified=stratified)
        total_samples = len(df)

        completed_ids = self.get_existing_completed_ids()
        print(f"\n=======================================================")
        print(f"BẮT ĐẦU BENCHMARK INFERENCE ({self.model_provider.model_name})")
        print(f"Chế độ (Mode): {self.mode.upper()}")
        if self.mode == "legacy-rag":
            print(f"RAG Legacy: BẬT (top_k={self.rag_top_k}, threshold={self.rag_threshold})")
        elif self.mode == "normalization-rag":
            print(f"RAG Normalization: BẬT (Dictionary + Boundary Pattern Matching)")
        else:
            print(f"RAG: TẮT (Baseline raw text)")
        print(f"Tổng số mẫu cần chạy: {total_samples}")
        print(f"Số mẫu đã có sẵn (sẽ bỏ qua): {len(completed_ids)}")
        print(f"File lưu predictions: {self.predictions_file}")
        print(f"=======================================================\n")

        latencies = []
        input_token_counts = []
        output_token_counts = []
        success_count = 0
        fail_count = 0
        records = []

        start_benchmark_time = time.perf_counter()

        with open(self.predictions_file, "a", encoding="utf-8") as f_out:
            for _, row in tqdm(df.iterrows(), total=total_samples, desc="Inference"):
                s_id = str(row["id"])
                text = str(row["text"]).strip()
                b_type = str(row.get("business_type", "PRODUCER"))

                # Resume: Bỏ qua nếu mẫu đã có trong predictions
                if s_id in completed_ids:
                    continue

                raw_text = text
                normalized_text = text
                normalization_changes = {}
                knowledge = ""
                input_to_model = raw_text

                # 1. Xử lý theo từng mode
                if self.mode == "normalization-rag" and self.normalizer:
                    normalized_text, normalization_changes = self.normalizer.normalize(raw_text)
                    input_to_model = normalized_text
                    # Kiến trúc mới: Qwen nhận normalized_text và instruction tối giản, KHÔNG nhồi context dài
                    knowledge = ""
                elif self.mode == "legacy-rag" and self.rag_service:
                    try:
                        knowledge = self.rag_service.build_context(
                            raw_text,
                            top_k=self.rag_top_k,
                            similarity_threshold=self.rag_threshold
                        )
                    except Exception as e:
                        print(f"[Warning] Lỗi trích xuất RAG context cho mẫu {s_id}: {e}")
                    input_to_model = raw_text
                else:
                    # mode no-rag
                    input_to_model = raw_text
                    knowledge = ""

                # 2. Dự đoán qua Model Provider
                res = self.model_provider.predict(input_to_model, business_type=b_type, knowledge=knowledge)
                raw_pred = res.get("prediction", {})
                normalized_pred = deterministic_normalize_prediction(raw_pred, text=input_to_model)

                latency = res.get("latency_ms", 0.0)
                in_tok = res.get("input_tokens")
                out_tok = res.get("output_tokens")
                err = res.get("error")

                latencies.append(latency)
                if in_tok is not None:
                    input_token_counts.append(in_tok)
                if out_tok is not None:
                    output_token_counts.append(out_tok)

                if err is None:
                    success_count += 1
                else:
                    fail_count += 1

                record = {
                    "id": s_id,
                    "text": text,
                    "raw_text": raw_text,
                    "normalized_text": normalized_text,
                    "normalization_changes": normalization_changes if normalization_changes else None,
                    "mode": self.mode,
                    "business_type": b_type,
                    "knowledge": knowledge if knowledge else None,
                    "prediction": normalized_pred,
                    "latency_ms": latency,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "error": err
                }
                records.append(record)

                # Ghi streaming lập tức và flush để chống mất dữ liệu khi ngắt kết nối
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                f_out.flush()

                if delay_seconds > 0:
                    time.sleep(delay_seconds)

        total_duration = time.perf_counter() - start_benchmark_time
        new_samples_run = len(latencies)

        # Tính toán thống kê hiệu năng
        avg_lat = sum(latencies) / new_samples_run if new_samples_run > 0 else 0.0
        sorted_lat = sorted(latencies) if latencies else [0.0]
        p50 = sorted_lat[int(0.50 * len(sorted_lat))] if latencies else 0.0
        p95 = sorted_lat[int(0.95 * len(sorted_lat))] if latencies else 0.0
        min_lat = sorted_lat[0] if latencies else 0.0
        max_lat = sorted_lat[-1] if latencies else 0.0
        throughput = (new_samples_run / total_duration) if total_duration > 0 else 0.0

        hw_info = self.model_provider.get_hardware_info()

        summary = {
            "model_name": self.model_provider.model_name,
            "provider": getattr(self.model_provider, "provider_name", "unknown"),
            "mode": self.mode,
            "total_target_samples": total_samples,
            "already_completed": len(completed_ids),
            "newly_evaluated": new_samples_run,
            "successful_samples": success_count,
            "failed_samples": fail_count,
            "total_duration_sec": round(total_duration, 2),
            "throughput_samples_per_sec": round(throughput, 2),
            "avg_latency_ms": round(avg_lat, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "min_latency_ms": round(min_lat, 2),
            "max_latency_ms": round(max_lat, 2),
            "total_input_tokens": sum(input_token_counts) if input_token_counts else None,
            "total_output_tokens": sum(output_token_counts) if output_token_counts else None,
            "hardware": hw_info
        }


        # Lưu benchmark_summary.json
        summary_path = BenchmarkConfig.OUTPUT_DIR / "benchmark_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as f_s:
            json.dump(summary, f_s, ensure_ascii=False, indent=2)

        print("\n[✓] Hoàn thành benchmark inference!")
        print(f"    Số mẫu mới hoàn thành : {new_samples_run}")
        print(f"    Thời gian chạy        : {total_duration:.2f}s ({throughput:.2f} mẫu/s)")
        print(f"    Độ trễ trung bình     : {avg_lat:.2f} ms (p95: {p95:.2f} ms)")
        print(f"    Kết quả đã lưu tại    : {self.predictions_file}")
        print(f"    Tóm tắt hiệu năng     : {summary_path}")

        return summary
