import argparse
import sys
import os
import json
from pathlib import Path

# Đảm bảo root dir nằm trong sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_benchmark.config import BenchmarkConfig
from ai_benchmark.models import get_model_provider
from ai_benchmark.inference import BenchmarkPredictor
from ai_benchmark.evaluation import BenchmarkEvaluator


def parse_args():
    parser = argparse.ArgumentParser(description="VoiceCash NLP Benchmark (Llama 3.1 8B & Groq)")

    parser.add_argument(
        "--model-provider",
        type=str,
        default=BenchmarkConfig.MODEL_PROVIDER,
        choices=["llama_local", "groq", "ollama"],
        help="Provider mô hình: 'llama_local', 'groq' hoặc 'ollama' (mặc định: từ config hoặc llama_local)"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Tên mô hình (ví dụ: meta-llama/Llama-3.2-3B-Instruct, llama3.2:3b, openai/gpt-oss-120b)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(BenchmarkConfig.DEFAULT_DATASET_PATH),
        help="Đường dẫn file CSV dataset (mặc định: ai_benchmark/datasets/voicecash_producer_1000.csv)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Số lượng mẫu đầu tiên cần chạy"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Số lượng mẫu lấy ngẫu nhiên"
    )
    parser.add_argument(
        "--stratified",
        action="store_true",
        help="Bật phân tầng theo intent khi lấy sample"
    )
    parser.add_argument(
        "--predictions-file",
        type=str,
        default=None,
        help="Đường dẫn file JSONL lưu kết quả dự đoán (mặc định tự động sinh theo tên mô hình)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(BenchmarkConfig.OUTPUT_DIR),
        help="Thư mục xuất báo cáo đánh giá"
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Chỉ chạy offline evaluation trên file predictions có sẵn, không gọi LLM inference"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Độ trễ (giây) giữa các request (hữu ích cho Groq tránh rate limit)"
    )
    parser.add_argument(
        "--load-in-4bit",
        type=str,
        default=None,
        choices=["true", "false", "1", "0"],
        help="Bật/tắt 4-bit quantization cho Llama local"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["no-rag", "legacy-rag", "normalization-rag"],
        help="Chế độ RAG: 'no-rag' (baseline), 'legacy-rag' (nhồi chunks vào prompt), 'normalization-rag' (chuẩn hóa trước khi gọi LLM)"
    )
    parser.add_argument(
        "--use-rag",
        action="store_true",
        default=BenchmarkConfig.USE_RAG,
        help="Bật trích xuất tri thức từ RAG (tương đương --mode legacy-rag, giữ tương thích ngược)"
    )
    parser.add_argument(
        "--rag-top-k",
        type=int,
        default=BenchmarkConfig.RAG_TOP_K,
        help="Số lượng context chunk RAG tối đa cần lấy (mặc định: 2)"
    )
    parser.add_argument(
        "--rag-threshold",
        type=float,
        default=BenchmarkConfig.RAG_THRESHOLD,
        help="Ngưỡng similarity tối thiểu cho RAG (mặc định: 0.40)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Chạy chế độ thử nghiệm tương tác trong terminal VS Code (gõ câu nói trực tiếp)"
    )
    parser.add_argument(
        "--text", "-t",
        type=str,
        default=None,
        help="Chạy dự đoán trực tiếp cho một câu giao dịch cụ thể được nhập từ dòng lệnh"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Chạy lại từ đầu (xóa bỏ dữ liệu cũ trong file predictions, không dùng resume)"
    )

    return parser.parse_args()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    # 1. Chế độ CHỈ ĐÁNH GIÁ (Offline Evaluation Only)
    if args.eval_only:
        if not args.predictions_file:
            print("[Error] Vui lòng chỉ định --predictions-file khi dùng cờ --eval-only.")
            sys.exit(1)

        print(f"[*] Bắt đầu đánh giá offline từ: {args.predictions_file}")
        evaluator = BenchmarkEvaluator(
            dataset_path=args.dataset,
            output_dir=args.output_dir
        )
        results = evaluator.evaluate(predictions_path=args.predictions_file)
        evaluator.print_summary(results)
        print(f"[✓] Đã xuất báo cáo tại: {args.output_dir}")
        return

    # 2. Khởi tạo Model Provider
    model_name = args.model_name
    if not model_name:
        if args.model_provider == "groq":
            model_name = "openai/gpt-oss-120b"
        elif args.model_provider == "ollama":
            model_name = "llama3.1:latest"
        else:
            model_name = BenchmarkConfig.MODEL_NAME

    kwargs = {}
    if args.load_in_4bit is not None:
        kwargs["load_in_4bit"] = args.load_in_4bit in ("true", "1")

    print(f"[*] Khởi tạo Provider: {args.model_provider} (Model: {model_name})")
    model_provider = get_model_provider(
        provider_name=args.model_provider,
        model_name=model_name,
        **kwargs
    )

    # Xác định effective_mode (ưu tiên --mode, fallback --use-rag, mặc định no-rag)
    if args.mode:
        effective_mode = args.mode
    elif args.use_rag:
        effective_mode = "legacy-rag"
    else:
        effective_mode = BenchmarkConfig.BENCHMARK_MODE

    # 3. Chế độ TƯƠNG TÁC hoặc CHẠY 1 CÂU TỰ NHẬP (--text / --interactive)
    if args.text or args.interactive:
        try:
            from ai_benchmark.evaluation.normalization import deterministic_normalize_prediction
        except ImportError:
            from evaluation.normalization import deterministic_normalize_prediction

        rag_service = None
        normalizer = None

        if effective_mode == "normalization-rag":
            try:
                try:
                    # pyrefly: ignore [missing-import]
                    from app.ai.rag.normalization_service import NormalizationService
                except ImportError:
                    try:
                        from ai_benchmark.rag.normalization_service import NormalizationService
                    except ImportError:
                        from rag.normalization_service import NormalizationService
                print("[*] Đang nạp Normalization Service...")
                normalizer = NormalizationService()
                print("[✓] Normalization Service sẵn sàng.\n")
            except Exception as e:
                print(f"[!] Lỗi nạp Normalization Service: {e}\n")

        elif effective_mode == "legacy-rag":
            try:
                try:
                    # pyrefly: ignore [missing-import]
                    from app.ai.rag.rag_service import RAGService
                    # pyrefly: ignore [missing-import]
                    from app.ai.rag.vector_store import VectorStore
                except ImportError:
                    try:
                        from ai_benchmark.rag.rag_service import RAGService
                        from ai_benchmark.rag.vector_store import VectorStore
                    except ImportError:
                        from rag.rag_service import RAGService
                        from rag.vector_store import VectorStore
                print("[*] Đang nạp Legacy RAG Vector Store...")
                vs = VectorStore(
                    knowledge_path=str(BenchmarkConfig.RAG_KNOWLEDGE_PATH),
                    persist_path=str(BenchmarkConfig.RAG_CHROMA_PATH)
                )
                rag_service = RAGService(vector_store=vs)
                print("[✓] Legacy RAG Service sẵn sàng.\n")
            except Exception as e:
                print(f"[!] Không thể nạp RAG: {e}\n")

        def run_single_inference(user_text: str):
            knowledge = ""
            input_to_model = user_text

            if effective_mode == "normalization-rag" and normalizer:
                input_to_model, changes = normalizer.normalize(user_text)
                if changes:
                    print(f"[Normalization RAG] '{user_text}' ──► '{input_to_model}' (Thay đổi: {changes})")
                knowledge = ""
            elif effective_mode == "legacy-rag" and rag_service:
                try:
                    knowledge = rag_service.build_context(
                        user_text,
                        top_k=args.rag_top_k,
                        similarity_threshold=args.rag_threshold
                    )
                    if knowledge:
                        print(f"[RAG Context] {knowledge.strip()}")
                except Exception as e:
                    print(f"[!] Lỗi RAG: {e}")

            res = model_provider.predict(input_to_model, knowledge=knowledge)
            raw_pred = res.get("prediction", {})
            pred = deterministic_normalize_prediction(raw_pred, text=input_to_model)
            latency = res.get("latency_ms", 0.0)

            from ai_benchmark.evaluation.normalization import to_transaction_row
            row_15 = to_transaction_row(pred, s_id="", text=user_text, business_type=getattr(args, "business_type", "PRODUCER"))

            print(f"\n--- KẾT QUẢ TRÍCH XUẤT ({latency/1000.0:.2f}s) ---")
            print(json.dumps(pred, ensure_ascii=False, indent=2))
            print("\n[15 FIELDS CHUẨN VOICECASH]:")
            for k, v in row_15.items():
                print(f"  • {k:<18}: {v}")
            print("------------------------------------\n")
            return pred

        # Nếu người dùng truyền --text trực tiếp từ dòng lệnh
        if args.text:
            run_single_inference(args.text.strip())
            return

        # Nếu người dùng chạy interactive loop
        print("\n" + "=" * 60)
        print(f"CHẾ ĐỘ TƯƠNG TÁC TRỰC TIẾP TRÊN VS CODE ({model_name})")
        print(f"Chế độ RAG: {effective_mode.upper()}")
        print("Gõ câu giao dịch tiếng Việt và nhấn Enter. Gõ 'q' hoặc 'exit' để thoát.")
        print("=" * 60 + "\n")

        while True:
            try:
                user_text = input("[VoiceCash Input] > ").strip()
                if not user_text:
                    continue
                if user_text.lower() in ("exit", "quit", "q"):
                    print("Kết thúc phiên tương tác. Tạm biệt!")
                    break
                run_single_inference(user_text)
            except KeyboardInterrupt:
                print("\nĐã ngắt phiên tương tác.")
                break
            except Exception as e:
                print(f"[Lỗi] {e}\n")
        return

    # 4. Chạy Batch Inference & Streaming Persistence
    predictor = BenchmarkPredictor(
        model_provider=model_provider,
        predictions_file=args.predictions_file,
        dataset_path=args.dataset,
        mode=effective_mode,
        use_rag=args.use_rag,
        rag_top_k=args.rag_top_k,
        rag_threshold=args.rag_threshold,
        force=args.force
    )

    predictor.run(
        limit=args.limit,
        sample=args.sample,
        stratified=args.stratified,
        delay_seconds=args.delay
    )

    # 4. Tự động chạy Offline Evaluation sau khi xong inference
    print("\n[*] Đang tính toán chỉ số đánh giá offline...")
    evaluator = BenchmarkEvaluator(
        dataset_path=args.dataset,
        output_dir=args.output_dir
    )
    results = evaluator.evaluate(predictions_path=predictor.predictions_file)
    evaluator.print_summary(results)

    print(f"[✓] Tất cả báo cáo đã được lưu vào thư mục: {args.output_dir}")


if __name__ == "__main__":
    main()
