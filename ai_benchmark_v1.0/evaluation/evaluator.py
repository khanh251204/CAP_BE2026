# evaluation/evaluator.py
import os
import json
import time
import pandas as pd
from typing import Dict, List, Any, Optional
from tqdm import tqdm

from app.ai.llm.groq_service import GroqService
from evaluation.metrics import (
    normalize_intent,
    calculate_classification_metrics,
    calculate_entity_metrics,
    is_match_price,
    is_match_text,
    normalize_unit,
)
from evaluation.report_exporter import (
    print_evaluation_summary,
    save_markdown_report_to_file,
)


class NLPEvaluator:
    """
    Evaluator cho mô hình NLP VoiceCashBook chạy bằng Groq.
    Đánh giá Intent Classification và Entity Extraction (Slot Filling)
    với 4 chỉ số chính: Accuracy, Precision, Recall, F1-Score.
    """

    def __init__(
        self,
        csv_path: str = "evaluation/voicecash_producer_1000.csv",
        cache_path: str = "evaluation/groq_predictions_cache.json",
        model_name: Optional[str] = None,
        delay_seconds: float = 0.5,
    ):
        self.csv_path = csv_path
        self.cache_path = cache_path
        self.delay_seconds = delay_seconds

        self.groq_service = GroqService()
        if model_name:
            self.groq_service.analysis_model = model_name
        self.model_name = self.groq_service.analysis_model

        self.cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Warning] Không thể đọc cache {self.cache_path}: {e}")
        return {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def load_dataset(self, limit: Optional[int] = None) -> pd.DataFrame:
        if not os.path.exists(self.csv_path):
            alt_path = os.path.join("app", "ai", self.csv_path)
            if os.path.exists(alt_path):
                self.csv_path = alt_path
            else:
                raise FileNotFoundError(f"Không tìm thấy file: {self.csv_path}")

        df = pd.read_csv(self.csv_path)
        if limit and limit > 0:
            df = df.head(limit)
        return df

    def predict_one(self, text: str, max_retries: int = 3) -> Dict[str, Any]:
        cache_key = text.strip()
        if cache_key in self.cache:
            return self.cache[cache_key]

        for attempt in range(max_retries):
            try:
                res = self.groq_service.analyze_transaction(text)
                self.cache[cache_key] = res
                return res
            except Exception as e:
                wait_time = (attempt + 1) * 2
                print(f"[Retry {attempt+1}/{max_retries}] Lỗi: {e}. Đợi {wait_time}s...")
                time.sleep(wait_time)

        fallback = {
            "status": "error",
            "text": text,
            "intent": "unknown",
            "type": "none",
            "entities": {},
            "missing_fields": [],
            "message": "API call failed"
        }
        self.cache[cache_key] = fallback
        return fallback

    def run_evaluation(
        self,
        limit: Optional[int] = None,
        save_predictions_csv: Optional[str] = "evaluation/predictions.csv"
    ) -> Dict[str, Any]:
        df = self.load_dataset(limit=limit)
        total = len(df)
        print(f"\n=======================================================")
        print(f"BẮT ĐẦU ĐÁNH GIÁ NLP GROQ TRÊN TẬP DỮ LIỆU ({total} mẫu)")
        print(f"Mô hình: {self.model_name}")
        print(f"Dataset: {self.csv_path}")
        print(f"=======================================================\n")

        y_true_intent = []
        y_pred_intent = []
        true_entities_list = []
        pred_entities_list = []
        predictions_records = []
        exact_match_count = 0

        for idx, row in tqdm(df.iterrows(), total=total, desc="Evaluating"):
            text = str(row["text"]).strip()
            true_intent = str(row.get("intent", "")).strip()

            pred = self.predict_one(text)
            pred_intent_raw = pred.get("intent", "unknown")
            pred_entities = pred.get("entities", {}) or {}

            norm_true_intent = normalize_intent(true_intent)
            norm_pred_intent = normalize_intent(pred_intent_raw)

            y_true_intent.append(norm_true_intent)
            y_pred_intent.append(norm_pred_intent)

            t_entities = {
                "product": row.get("product") if pd.notna(row.get("product")) else None,
                "price": row.get("price") if pd.notna(row.get("price")) else None,
                "quantity": row.get("quantity") if pd.notna(row.get("quantity")) else None,
                "unit": row.get("unit") if pd.notna(row.get("unit")) else None,
                "customer": row.get("customer") if pd.notna(row.get("customer")) else None,
                "supplier": row.get("supplier") if pd.notna(row.get("supplier")) else None,
                "date": row.get("date") if pd.notna(row.get("date")) else None,
            }
            true_entities_list.append(t_entities)
            pred_entities_list.append(pred_entities)

            intent_correct = (norm_true_intent == norm_pred_intent)
            all_entities_correct = True
            for k, tv in t_entities.items():
                pv = pred_entities.get(k)
                if tv is not None:
                    if pv is None:
                        all_entities_correct = False
                        break
                    if k == "price" and not is_match_price(pv, tv, t_entities.get("quantity")):
                        all_entities_correct = False
                        break
                    elif k == "quantity":
                        try:
                            if float(pv) != float(tv):
                                all_entities_correct = False
                                break
                        except Exception:
                            all_entities_correct = False
                            break
                    elif k == "unit" and normalize_unit(pv) != normalize_unit(tv):
                        all_entities_correct = False
                        break
                    elif k not in ["price", "quantity", "unit"] and not is_match_text(pv, tv):
                        all_entities_correct = False
                        break

            is_exact = intent_correct and all_entities_correct
            if is_exact:
                exact_match_count += 1

            predictions_records.append({
                "id": row.get("id", idx + 1),
                "text": text,
                "true_intent": true_intent,
                "pred_intent": pred_intent_raw,
                "intent_match": intent_correct,
                "exact_match": is_exact,
                "pred_entities": json.dumps(pred_entities, ensure_ascii=False),
                "true_product": t_entities["product"],
                "pred_product": pred_entities.get("product"),
                "true_price": t_entities["price"],
                "pred_price": pred_entities.get("price"),
                "true_quantity": t_entities["quantity"],
                "pred_quantity": pred_entities.get("quantity"),
                "true_unit": t_entities["unit"],
                "pred_unit": pred_entities.get("unit"),
                "true_customer": t_entities["customer"],
                "pred_customer": pred_entities.get("customer"),
                "true_supplier": t_entities["supplier"],
                "pred_supplier": pred_entities.get("supplier"),
                "true_date": t_entities["date"],
                "pred_date": pred_entities.get("date"),
            })

            if (idx + 1) % 10 == 0:
                self._save_cache()

            if self.delay_seconds > 0 and text not in self.cache:
                time.sleep(self.delay_seconds)

        self._save_cache()

        if save_predictions_csv:
            os.makedirs(os.path.dirname(save_predictions_csv) or ".", exist_ok=True)
            pd.DataFrame(predictions_records).to_csv(save_predictions_csv, index=False, encoding="utf-8")

        intent_metrics = calculate_classification_metrics(y_true_intent, y_pred_intent)
        entity_metrics = calculate_entity_metrics(true_entities_list, pred_entities_list)

        return {
            "model": self.model_name,
            "total_samples": total,
            "sentence_exact_match_accuracy": round(exact_match_count / total, 4) if total > 0 else 0.0,
            "exact_match_count": exact_match_count,
            "intent_classification": intent_metrics,
            "entity_extraction": entity_metrics
        }

    def print_summary(self, results: Dict[str, Any]):
        print_evaluation_summary(results)

    def save_markdown_report(self, results: Dict[str, Any], output_file: str = "evaluation/evaluation_report.md"):
        save_markdown_report_to_file(results, self.csv_path, output_file)
