import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from ai_benchmark.config import BenchmarkConfig
from ai_benchmark.evaluation.normalization import normalize_intent, is_entity_match_normalized, remove_accents
from ai_benchmark.evaluation.metrics import (
    calculate_intent_metrics,
    calculate_entity_metrics,
    calculate_end_to_end_metrics,
    ENTITY_FIELDS
)
from ai_benchmark.evaluation.confusion_matrix import (
    generate_confusion_matrix,
    save_confusion_matrix_csv,
    format_confusion_matrix_markdown
)


class BenchmarkEvaluator:
    """
    Evaluator offline độc lập cho VoiceCash NLP Benchmark.
    Không gọi LLM, tính toán thuần túy bằng Python / scikit-learn từ predictions và ground truth.
    """

    def __init__(
        self,
        dataset_path: Optional[str | Path] = None,
        predictions_path: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None
    ):
        self.dataset_path = Path(dataset_path or BenchmarkConfig.DEFAULT_DATASET_PATH)
        self.predictions_path = Path(predictions_path) if predictions_path else None
        self.output_dir = Path(output_dir or BenchmarkConfig.OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_predictions_from_jsonl(self, jsonl_path: Path) -> Dict[Any, Dict[str, Any]]:
        """Đọc predictions từ file jsonl và index theo id."""
        records = {}
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file prediction: {jsonl_path}")

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    records[str(obj["id"])] = obj
                except Exception as e:
                    print(f"[Warning] Bỏ qua dòng json lỗi: {e}")

        return records

    def evaluate(
        self,
        predictions_records: Optional[List[Dict[str, Any]]] = None,
        predictions_path: Optional[str | Path] = None
    ) -> Dict[str, Any]:
        """
        Thực hiện đánh giá toàn diện.
        Có thể nhận trực tiếp list các bản ghi hoặc đường dẫn tới file JSONL.
        """
        if predictions_path:
            self.predictions_path = Path(predictions_path)

        df = pd.read_csv(self.dataset_path)

        # Map predictions by ID
        if predictions_records:
            pred_map = {str(r["id"]): r for r in predictions_records}
        elif self.predictions_path:
            pred_map = self.load_predictions_from_jsonl(self.predictions_path)
        else:
            raise ValueError("Cần cung cấp predictions_records hoặc predictions_path.")

        y_true_intent_raw = []
        y_pred_intent_raw = []
        y_true_intent_norm = []
        y_pred_intent_norm = []

        true_entities_list = []
        pred_entities_list = []
        matched_samples = 0

        failed_samples = []
        dataset_warnings = []

        for _, row in df.iterrows():
            s_id = str(row["id"])
            if s_id not in pred_map:
                continue

            matched_samples += 1
            rec = pred_map[s_id]
            text = str(row.get("text", ""))
            pred_data = rec.get("prediction", {}) or {}

            raw_true_intent = str(row.get("intent", "khac")).strip()
            raw_pred_intent = str(pred_data.get("intent", "khac")).strip()

            t_intent_norm = normalize_intent(raw_true_intent)
            p_intent_norm = normalize_intent(raw_pred_intent)

            y_true_intent_raw.append(raw_true_intent)
            y_pred_intent_raw.append(raw_pred_intent)
            y_true_intent_norm.append(t_intent_norm)
            y_pred_intent_norm.append(p_intent_norm)

            t_ents = {}
            for col in ENTITY_FIELDS:
                val = row.get(col)
                if pd.notna(val) and str(val).strip() != "":
                    t_ents[col] = val
                else:
                    t_ents[col] = None

            p_ents = pred_data.get("entities", {}) or {}
            true_entities_list.append(t_ents)
            pred_entities_list.append(p_ents)

            # Error analysis & category tracking
            failed_fields = []
            error_categories = []
            if t_intent_norm != p_intent_norm:
                failed_fields.append("intent")
                error_categories.append("intent_error")

            for col in ENTITY_FIELDS:
                matched = is_entity_match_normalized(
                    col,
                    p_ents.get(col),
                    t_ents.get(col),
                    quantity=t_ents.get("quantity") or p_ents.get("quantity")
                )
                if not matched:
                    failed_fields.append(col)
                    error_categories.append(f"{col}_error")

            raw_text = rec.get("raw_text") or text
            normalized_text = rec.get("normalized_text") or text
            normalization_changes = rec.get("normalization_changes") or {}
            mode = rec.get("mode") or "unknown"

            if failed_fields:
                failed_samples.append({
                    "id": s_id,
                    "text": text,
                    "raw_text": raw_text,
                    "normalized_text": normalized_text,
                    "normalization_changes": normalization_changes,
                    "mode": mode,
                    "expected": {"intent": t_intent_norm, **t_ents},
                    "predicted": {"intent": p_intent_norm, **p_ents},
                    "failed_fields": failed_fields,
                    "error_category": error_categories
                })

            # Check POSSIBLE_DATASET_ISSUE
            # 1. Customer hallucination in ground truth
            t_cust = t_ents.get("customer")
            if t_cust and remove_accents(str(t_cust)) not in remove_accents(text):
                dataset_warnings.append({
                    "sample_id": s_id,
                    "field": "customer",
                    "ground_truth": t_cust,
                    "prediction": p_ents.get("customer"),
                    "reason": f"Customer '{t_cust}' in ground truth is absent from user utterance '{text}'"
                })

            # 2. Intraday time expressions in ground truth date
            t_date = t_ents.get("date")
            if t_date:
                t_date_norm = remove_accents(str(t_date)).strip()
                if t_date_norm in ("chieu nay", "dau gio chieu", "moi nay", "cuoi ngay", "cuoi ngay hom nay", "sang nay", "trua nay", "luc 3 gio"):
                    dataset_warnings.append({
                        "sample_id": s_id,
                        "field": "date",
                        "ground_truth": t_date,
                        "prediction": p_ents.get("date"),
                        "reason": f"Ground truth date '{t_date}' is an intraday time expression rather than a calendar date."
                    })

            # 3. Product merged with unit prefix in ground truth
            t_prod = t_ents.get("product")
            if t_ents.get("unit") is None and t_prod:
                for prefix in ("cai ", "chai ", "cay ", "hop ", "lon "):
                    if str(t_prod).startswith(prefix):
                        dataset_warnings.append({
                            "sample_id": s_id,
                            "field": "unit",
                            "ground_truth": f"product='{t_prod}', unit=null",
                            "prediction": f"product='{p_ents.get('product')}', unit='{p_ents.get('unit')}'",
                            "reason": f"Ground truth merged packaging unit '{prefix.strip()}' into product name instead of separate unit field."
                        })
                        break

        if matched_samples == 0:
            raise ValueError("Không tìm thấy mẫu dự đoán nào khớp với dataset ID.")

        # 1. Intent Classification Metrics (Normalized)
        intent_metrics = calculate_intent_metrics(y_true_intent_norm, y_pred_intent_norm)

        # 2. Confusion Matrix
        cm_data = generate_confusion_matrix(y_true_intent_norm, y_pred_intent_norm)

        # 3. Entity Extraction Metrics
        entity_metrics = calculate_entity_metrics(true_entities_list, pred_entities_list)

        # 4. End-to-End Metrics
        e2e_metrics = calculate_end_to_end_metrics(
            y_true_intent_raw,
            y_pred_intent_raw,
            true_entities_list,
            pred_entities_list
        )

        # 5. Normalization Statistics
        normalized_count = sum(
            1 for rec in pred_map.values()
            if rec.get("normalization_changes") or (rec.get("raw_text") and rec.get("normalized_text") and rec.get("raw_text") != rec.get("normalized_text"))
        )
        normalization_stats = {
            "total_samples": matched_samples,
            "normalized_samples": normalized_count,
            "normalization_rate": round(normalized_count / matched_samples, 4) if matched_samples > 0 else 0.0
        }

        # 6. A/B Comparison (nếu có file baseline no-rag)
        ab_comparison = None
        if self.predictions_path and "_normalization_rag_" in self.predictions_path.name:
            candidates = [
                self.predictions_path.name.replace("_normalization_rag_", "_"),
                self.predictions_path.name.replace("_normalization_rag_", "_no_rag_")
            ]
            for c_name in candidates:
                baseline_file = self.predictions_path.parent / c_name
                if baseline_file.exists():
                    try:
                        baseline_preds = self.load_predictions_from_jsonl(baseline_file)
                        ab_comparison = self.compare_ab(baseline_preds, pred_map, df)
                        break
                    except Exception as e:
                        print(f"[Warning] Lỗi khi thực hiện so sánh A/B với baseline: {e}")


        results = {
            "total_evaluated_samples": matched_samples,
            "end_to_end": e2e_metrics,
            "intent_classification": intent_metrics,
            "entity_extraction": entity_metrics,
            "normalization_stats": normalization_stats,
            "ab_comparison": ab_comparison,
            "confusion_matrix": cm_data["matrix"],
            "confusion_matrix_labels": cm_data["labels"],
            "error_analysis": failed_samples,
            "dataset_warnings": dataset_warnings
        }

        # Export các artifact kết quả
        self._export_reports(results, cm_data["dataframe"])

        return results

    def compare_ab(
        self,
        baseline_preds: Dict[str, Any],
        experiment_preds: Dict[str, Any],
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        So sánh A/B giữa Baseline (No-RAG) và Experiment (Normalization RAG):
        Thống kê 5 Cases:
        - Case 1: RAG đúng -> Qwen đúng (Baseline sai, Experiment đúng nhờ RAG)
        - Case 2: RAG đúng -> Qwen vẫn sai (Baseline sai, Experiment vẫn sai dù RAG chuẩn hóa đúng)
        - Case 3: RAG sai -> Qwen sai
        - Case 4: RAG không thay đổi -> Qwen đúng / giữ nguyên
        - Case 5: RAG làm câu đúng thành sai (Baseline đúng, Experiment sai do RAG)
        """
        cases_breakdown = {
            "case_1_rag_correct_qwen_correct": [],
            "case_2_rag_correct_qwen_still_wrong": [],
            "case_3_rag_wrong_qwen_wrong": [],
            "case_4_rag_unchanged": [],
            "case_5_rag_degraded": []
        }

        improved_count = 0
        unchanged_count = 0
        degraded_count = 0

        common_ids = [str(r["id"]) for _, r in df.iterrows() if str(r["id"]) in baseline_preds and str(r["id"]) in experiment_preds]

        for s_id in common_ids:
            row = df[df["id"].astype(str) == s_id].iloc[0]
            base_rec = baseline_preds[s_id]
            exp_rec = experiment_preds[s_id]

            raw_text = exp_rec.get("raw_text") or str(row.get("text", ""))
            changes = exp_rec.get("normalization_changes") or {}

            # Kiểm tra độ chính xác E2E normalized của baseline
            base_intent_match = normalize_intent(row.get("intent")) == normalize_intent(base_rec.get("prediction", {}).get("intent"))
            base_ents_match = True
            for col in ENTITY_FIELDS:
                t_val = row.get(col)
                if pd.isna(t_val) or str(t_val).strip() == "":
                    t_val = None
                p_val = base_rec.get("prediction", {}).get("entities", {}).get(col)
                if not is_entity_match_normalized(col, p_val, t_val, quantity=t_val or p_val):
                    base_ents_match = False
                    break
            base_correct = base_intent_match and base_ents_match

            # Kiểm tra độ chính xác E2E normalized của experiment
            exp_intent_match = normalize_intent(row.get("intent")) == normalize_intent(exp_rec.get("prediction", {}).get("intent"))
            exp_ents_match = True
            for col in ENTITY_FIELDS:
                t_val = row.get(col)
                if pd.isna(t_val) or str(t_val).strip() == "":
                    t_val = None
                p_val = exp_rec.get("prediction", {}).get("entities", {}).get(col)
                if not is_entity_match_normalized(col, p_val, t_val, quantity=t_val or p_val):
                    exp_ents_match = False
                    break
            exp_correct = exp_intent_match and exp_ents_match

            # Phân loại 5 cases
            if not base_correct and exp_correct:
                improved_count += 1
                cases_breakdown["case_1_rag_correct_qwen_correct"].append({
                    "id": s_id,
                    "text": raw_text,
                    "changes": changes
                })
            elif base_correct and not exp_correct:
                degraded_count += 1
                cases_breakdown["case_5_rag_degraded"].append({
                    "id": s_id,
                    "text": raw_text,
                    "changes": changes
                })
            elif not base_correct and not exp_correct:
                if changes:
                    cases_breakdown["case_2_rag_correct_qwen_still_wrong"].append({
                        "id": s_id,
                        "text": raw_text,
                        "changes": changes
                    })
                unchanged_count += 1
            else:
                # Cả hai cùng đúng
                unchanged_count += 1
                cases_breakdown["case_4_rag_unchanged"].append({
                    "id": s_id,
                    "text": raw_text,
                    "changes": changes
                })

        return {
            "total_compared_samples": len(common_ids),
            "rag_improved": improved_count,
            "rag_unchanged": unchanged_count,
            "rag_degraded": degraded_count,
            "improvement_rate": round(improved_count / len(common_ids), 4) if common_ids else 0.0,
            "degradation_rate": round(degraded_count / len(common_ids), 4) if common_ids else 0.0,
            "cases_breakdown": cases_breakdown
        }


    def _export_reports(self, results: Dict[str, Any], df_cm: pd.DataFrame):
        """Xuất báo cáo dưới dạng JSON, CSV và Markdown."""
        # 1. evaluation_report.json
        json_path = self.output_dir / "evaluation_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # 2. classification_report.csv
        per_class = results["intent_classification"].get("per_class", {})
        if per_class:
            df_intent = pd.DataFrame.from_dict(per_class, orient="index")
            df_intent.index.name = "intent"
            df_intent.to_csv(self.output_dir / "classification_report.csv", encoding="utf-8")

        # 3. entity_metrics.csv
        per_entity = results["entity_extraction"].get("per_entity", {})
        if per_entity:
            df_entity = pd.DataFrame.from_dict(per_entity, orient="index")
            df_entity.index.name = "entity"
            df_entity.to_csv(self.output_dir / "entity_metrics.csv", encoding="utf-8")

        # 4. confusion_matrix.csv
        save_confusion_matrix_csv(df_cm, str(self.output_dir / "confusion_matrix.csv"))

        # 5. error_analysis.json & error_analysis.jsonl
        error_analysis_path = self.output_dir / "error_analysis.json"
        with open(error_analysis_path, "w", encoding="utf-8") as f:
            json.dump(results.get("error_analysis", []), f, ensure_ascii=False, indent=2)

        error_jsonl_path = self.output_dir / "error_analysis.jsonl"
        with open(error_jsonl_path, "w", encoding="utf-8") as f:
            for err_sample in results.get("error_analysis", []):
                failed_fields = err_sample.get("failed_fields", [])
                err_categories = err_sample.get("error_category", [])

                exp = err_sample.get("expected", {})
                pred = err_sample.get("predicted", {})
                is_hallucination = any(exp.get(f) is None and pred.get(f) is not None for f in ("date", "payment", "customer", "supplier"))

                primary_err = "hallucination" if is_hallucination else (err_categories[0] if err_categories else "unknown_error")
                raw_t = err_sample.get("raw_text") or err_sample.get("text", "")
                norm_t = err_sample.get("normalized_text") or raw_t
                changed_by_norm = (raw_t != norm_t) or bool(err_sample.get("normalization_changes"))

                jsonl_obj = {
                    "id": err_sample["id"],
                    "raw_text": raw_t,
                    "normalized_text": norm_t,
                    "expected": exp,
                    "predicted": pred,
                    "failed_fields": failed_fields,
                    "error_type": primary_err,
                    "error_categories": err_categories,
                    "changed_by_normalization": changed_by_norm
                }
                f.write(json.dumps(jsonl_obj, ensure_ascii=False) + "\n")

        # 6. dataset_warnings.json
        warnings_path = self.output_dir / "dataset_warnings.json"
        with open(warnings_path, "w", encoding="utf-8") as f:
            json.dump(results.get("dataset_warnings", []), f, ensure_ascii=False, indent=2)


        # 7. evaluation_report.md
        self._export_markdown_report(results, df_cm)

    def _export_markdown_report(self, results: Dict[str, Any], df_cm: pd.DataFrame):
        """Tạo file Markdown tóm tắt báo cáo trực quan."""
        e2e = results["end_to_end"]
        intent = results["intent_classification"]
        entity = results["entity_extraction"]
        failed_samples = results.get("error_analysis", [])
        dataset_warnings = results.get("dataset_warnings", [])

        md = f"""# VoiceCash Benchmark Evaluation Report

- **Total Evaluated Samples**: {results['total_evaluated_samples']}
- **Strict Match E2E Accuracy**: **{e2e['strict_match_accuracy'] * 100:.2f}%** ({e2e['strict_match_count']}/{e2e['total_samples']})
- **Normalized Match E2E Accuracy**: **{e2e['normalized_match_accuracy'] * 100:.2f}%** ({e2e['normalized_match_count']}/{e2e['total_samples']})

---

## 1. Intent Classification Metrics

| Metric | Giá trị |
| :--- | :--- |
| **Accuracy** | **{intent['accuracy'] * 100:.2f}%** |
| **Macro Precision** | {intent['macro_precision'] * 100:.2f}% |
| **Macro Recall** | {intent['macro_recall'] * 100:.2f}% |
| **Macro F1-Score** | **{intent['macro_f1'] * 100:.2f}%** |
| **Weighted F1-Score** | {intent['weighted_f1'] * 100:.2f}% |

### Chi tiết từng Intent:
| Intent | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
"""
        for it, vals in intent.get("per_class", {}).items():
            md += f"| `{it}` | {vals['precision']:.4f} | {vals['recall']:.4f} | **{vals['f1']:.4f}** | {vals['support']} |\n"

        md += f"""
---

## 2. Confusion Matrix

{format_confusion_matrix_markdown(df_cm)}

---

## 3. Entity Extraction Metrics (Slot Filling)

- **Micro F1-Score**: **{entity['micro_f1'] * 100:.2f}%**
- **Macro F1-Score**: **{entity['macro_f1'] * 100:.2f}%**

### Chi tiết từng Entity:
| Entity | Precision | Recall | F1-Score | TP | FP | FN | Support |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for ent, vals in entity.get("per_entity", {}).items():
            md += f"| `{ent}` | {vals['precision']:.4f} | {vals['recall']:.4f} | **{vals['f1']:.4f}** | {vals['tp']} | {vals['fp']} | {vals['fn']} | {vals['support']} |\n"

        # 4. Error Analysis
        md += f"""
---

## 4. Error Analysis ({len(failed_samples)} Failed Samples)

| ID | Text | Failed Fields | Error Category | Expected | Predicted |
| :---: | :--- | :--- | :--- | :--- | :--- |
"""
        for fs in failed_samples:
            fields_str = ", ".join(fs["failed_fields"])
            cats_str = ", ".join(fs["error_category"])
            exp_str = f"`intent`: {fs['expected'].get('intent')}"
            for k in fs["failed_fields"]:
                if k != "intent":
                    exp_str += f", `{k}`: {fs['expected'].get(k)}"
            pred_str = f"`intent`: {fs['predicted'].get('intent')}"
            for k in fs["failed_fields"]:
                if k != "intent":
                    pred_str += f", `{k}`: {fs['predicted'].get(k)}"

            clean_t = fs['text'].replace('|', '/')
            md += f"| {fs['id']} | {clean_t} | {fields_str} | {cats_str} | {exp_str} | {pred_str} |\n"

        # 5. Normalization & A/B Comparison Section
        norm_stats = results.get("normalization_stats", {})
        ab_comp = results.get("ab_comparison")
        if norm_stats:
            md += f"""
---

## 5. Normalization RAG Statistics

- **Tỷ lệ câu được chuẩn hóa**: **{norm_stats.get('normalization_rate', 0.0) * 100:.2f}%** ({norm_stats.get('normalized_samples', 0)}/{norm_stats.get('total_samples', 0)} mẫu)
"""

        if ab_comp:
            md += f"""
---

## 6. A/B Comparison Analysis (Baseline No-RAG vs Normalization RAG)

| Metric | Giá trị |
| :--- | :--- |
| **Tổng số mẫu so sánh** | {ab_comp['total_compared_samples']} |
| **RAG Improved (Case 1)** | **{ab_comp['rag_improved']}** ({ab_comp['improvement_rate'] * 100:.2f}%) |
| **RAG Unchanged (Case 4 / Case 2)** | {ab_comp['rag_unchanged']} |
| **RAG Degraded (Case 5)** | {ab_comp['rag_degraded']} ({ab_comp['degradation_rate'] * 100:.2f}%) |

### Chi tiết các ca RAG Cải thiện (Case 1):
"""
            c1 = ab_comp.get("cases_breakdown", {}).get("case_1_rag_correct_qwen_correct", [])
            if c1:
                md += "| ID | Câu nói gốc | Các từ đã chuẩn hóa |\n| :---: | :--- | :--- |\n"
                for item in c1:
                    md += f"| {item['id']} | {item['text']} | {item['changes']} |\n"
            else:
                md += "*(Không có mẫu nào trong nhóm này)*\n"

            c5 = ab_comp.get("cases_breakdown", {}).get("case_5_rag_degraded", [])
            if c5:
                md += "\n### Chi tiết các ca RAG làm suy giảm (Case 5):\n| ID | Câu nói gốc | Các từ đã chuẩn hóa |\n| :---: | :--- | :--- |\n"
                for item in c5:
                    md += f"| {item['id']} | {item['text']} | {item['changes']} |\n"

        # 7. Dataset Warnings
        if dataset_warnings:
            md += f"""
---

## 7. Dataset Ground-Truth Inconsistencies ({len(dataset_warnings)} Warnings)
> [!WARNING]
> Các bất thường dưới đây nằm ở nhãn Ground-Truth của tập dữ liệu gốc, không phải lỗi mô hình.

| Sample ID | Field | Ground Truth | Prediction | Reason |
| :---: | :--- | :--- | :--- | :--- |
"""
            for dw in dataset_warnings:
                gt_val = str(dw['ground_truth']).replace('|', '/')
                pred_val = str(dw['prediction']).replace('|', '/')
                reason_val = str(dw['reason']).replace('|', '/')
                md += f"| {dw['sample_id']} | `{dw['field']}` | {gt_val} | {pred_val} | {reason_val} |\n"

        md_path = self.output_dir / "evaluation_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

    def print_summary(self, results: Dict[str, Any]):
        """In tóm tắt ngắn gọn ra terminal."""
        e2e = results["end_to_end"]
        intent = results["intent_classification"]
        entity = results["entity_extraction"]
        norm_stats = results.get("normalization_stats", {})
        ab_comp = results.get("ab_comparison")
        failed_count = len(results.get("error_analysis", []))
        warnings_count = len(results.get("dataset_warnings", []))

        print("\n=======================================================")
        print("               VOICECASH BENCHMARK SUMMARY             ")
        print("=======================================================")
        print(f"Tổng số mẫu đánh giá: {results['total_evaluated_samples']}")
        print(f"Strict E2E Match     : {e2e['strict_match_accuracy'] * 100:.2f}% ({e2e['strict_match_count']}/{e2e['total_samples']})")
        print(f"Normalized E2E Match : {e2e['normalized_match_accuracy'] * 100:.2f}% ({e2e['normalized_match_count']}/{e2e['total_samples']})")
        print("-------------------------------------------------------")
        print(f"Intent Accuracy      : {intent['accuracy'] * 100:.2f}%")
        print(f"Intent Macro F1      : {intent['macro_f1'] * 100:.2f}%")
        print(f"Intent Weighted F1   : {intent['weighted_f1'] * 100:.2f}%")
        print("-------------------------------------------------------")
        print(f"Entity Micro F1      : {entity['micro_f1'] * 100:.2f}%")
        print(f"Entity Macro F1      : {entity['macro_f1'] * 100:.2f}%")
        print("-------------------------------------------------------")
        print("Per-Field Entity F1:")
        for ent, vals in entity.get("per_entity", {}).items():
            print(f"  - {ent:<18}: {vals['f1'] * 100:6.2f}% (Support: {vals['support']})")
        print("-------------------------------------------------------")
        if norm_stats and norm_stats.get("normalized_samples", 0) > 0:
            print(f"Mẫu được chuẩn hóa   : {norm_stats['normalized_samples']}/{norm_stats['total_samples']} ({norm_stats['normalization_rate']*100:.1f}%)")
        if ab_comp:
            print("-------------------------------------------------------")
            print("A/B Impact Analysis (So với Baseline No-RAG):")
            print(f"  • RAG improved (Case 1) : +{ab_comp['rag_improved']} mẫu ({ab_comp['improvement_rate']*100:.1f}%)")
            print(f"  • RAG unchanged         :  {ab_comp['rag_unchanged']} mẫu")
            print(f"  • RAG degraded (Case 5) : -{ab_comp['rag_degraded']} mẫu ({ab_comp['degradation_rate']*100:.1f}%)")
        print("-------------------------------------------------------")
        print(f"Lỗi trích xuất (Failed)     : {failed_count} mẫu")
        if warnings_count > 0:
            print(f"Cảnh báo Ground-Truth (Warn): {warnings_count} trường hợp")
        print("=======================================================\n")

