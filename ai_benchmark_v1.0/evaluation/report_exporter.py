# evaluation/report_exporter.py
import os
from typing import Dict, Any


def print_evaluation_summary(results: Dict[str, Any]):
    """Hiển thị bảng tổng kết các chỉ số Accuracy, Precision, Recall, F1 trên terminal."""
    intent = results["intent_classification"]
    entity = results["entity_extraction"]
    total = results["total_samples"]

    print("\n" + "=" * 80)
    print(f"             BÁO CÁO ĐÁNH GIÁ DỰ ÁN NLP (GROQ: {results['model']})")
    print("=" * 80)
    print(f"Tổng số mẫu đánh giá: {total}")
    print(f"Sentence Exact Match Accuracy: {results['sentence_exact_match_accuracy'] * 100:.2f}% "
          f"({results['exact_match_count']}/{total} câu)")

    print("\n" + "-" * 80)
    print("1. INTENT CLASSIFICATION METRICS:")
    print("-" * 80)
    print(f"{'Intent Class':<20} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<10}")
    print("-" * 80)
    for c, m in intent["per_class"].items():
        print(f"{c:<20} | {m['precision']:<10.4f} | {m['recall']:<10.4f} | {m['f1']:<10.4f} | {m['support']:<10}")
    print("-" * 80)
    print(f"Accuracy (Overall)  : {intent['accuracy'] * 100:.2f}%")
    print(f"Macro Precision     : {intent['macro_precision'] * 100:.2f}%")
    print(f"Macro Recall        : {intent['macro_recall'] * 100:.2f}%")
    print(f"Macro F1-Score      : {intent['macro_f1'] * 100:.2f}%")
    print(f"Weighted F1-Score   : {intent['weighted_f1'] * 100:.2f}%")

    print("\n" + "-" * 80)
    print("2. ENTITY EXTRACTION (SLOT FILLING / NER) METRICS:")
    print("-" * 80)
    print(f"{'Entity':<15} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'TP':<6} | {'FP':<6} | {'FN':<6} | {'Support':<8}")
    print("-" * 80)
    for ent, m in entity["per_entity"].items():
        print(f"{ent:<15} | {m['precision']:<10.4f} | {m['recall']:<10.4f} | {m['f1']:<10.4f} | "
              f"{m['tp']:<6} | {m['fp']:<6} | {m['fn']:<6} | {m['support']:<8}")
    print("-" * 80)
    print(f"Entity Micro P / R / F1 : P={entity['micro_precision']*100:.2f}%, "
          f"R={entity['micro_recall']*100:.2f}%, F1={entity['micro_f1']*100:.2f}%")
    print(f"Entity Macro P / R / F1 : P={entity['macro_precision']*100:.2f}%, "
          f"R={entity['macro_recall']*100:.2f}%, F1={entity['macro_f1']*100:.2f}%")
    print("=" * 80 + "\n")


def save_markdown_report_to_file(results: Dict[str, Any], csv_path: str, output_file: str = "evaluation/evaluation_report.md"):
    """Lưu báo cáo chi tiết thành file Markdown."""
    intent = results["intent_classification"]
    entity = results["entity_extraction"]
    total = results["total_samples"]

    lines = [
        f"# Báo Cáo Đánh Giá Hiệu Năng Dự Án NLP Groq",
        f"",
        f"- **Mô hình Groq**: `{results['model']}`",
        f"- **Tập dữ liệu**: `{csv_path}`",
        f"- **Số lượng mẫu đánh giá**: `{total}`",
        f"- **Sentence Exact Match Accuracy**: **`{results['sentence_exact_match_accuracy'] * 100:.2f}%`** "
        f"({results['exact_match_count']}/{total})",
        f"",
        f"---",
        f"",
        f"## 1. Intent Classification (Phân loại ý định)",
        f"",
        f"| Metric | Giá trị |",
        f"| :--- | :--- |",
        f"| **Overall Accuracy** | **{intent['accuracy'] * 100:.2f}%** |",
        f"| **Macro Precision** | **{intent['macro_precision'] * 100:.2f}%** |",
        f"| **Macro Recall** | **{intent['macro_recall'] * 100:.2f}%** |",
        f"| **Macro F1-Score** | **{intent['macro_f1'] * 100:.2f}%** |",
        f"| **Weighted F1-Score** | **{intent['weighted_f1'] * 100:.2f}%** |",
        f"",
        f"### Chi tiết theo từng Intent:",
        f"",
        f"| Intent | Precision | Recall | F1-Score | Support |",
        f"| :--- | :--- | :--- | :--- | :--- |",
    ]

    for c, m in intent["per_class"].items():
        lines.append(f"| `{c}` | {m['precision']:.4f} | {m['recall']:.4f} | **{m['f1']:.4f}** | {m['support']} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 2. Entity Extraction (Trích xuất thực thể / Slot Filling)",
        f"",
        f"| Entity | Precision | Recall | F1-Score | TP | FP | FN | Support |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for ent, m in entity["per_entity"].items():
        lines.append(
            f"| `{ent}` | {m['precision']:.4f} | {m['recall']:.4f} | **{m['f1']:.4f}** | "
            f"{m['tp']} | {m['fp']} | {m['fn']} | {m['support']} |"
        )

    lines.extend([
        f"",
        f"### Tổng hợp Entity Extraction:",
        f"- **Micro Precision**: `{entity['micro_precision'] * 100:.2f}%`",
        f"- **Micro Recall**: `{entity['micro_recall'] * 100:.2f}%`",
        f"- **Micro F1-Score**: **`{entity['micro_f1'] * 100:.2f}%`**",
        f"- **Macro F1-Score**: **`{entity['macro_f1'] * 100:.2f}%`**",
        f"",
        f"---",
        f"",
        f"## 3. Nhận xét và Phân tích lỗi",
        f"- Đánh giá dựa trên tập dữ liệu sản xuất của VoiceCashBook (`PRODUCER`).",
        f"- Tỷ lệ nhận diện các intent giao dịch cốt lõi (`ban_hang`, `nhap_hang`, `chi_phi`).",
        f"- Độ chính xác trích xuất thực thể số lượng (`quantity`), giá bán (`price`), và sản phẩm (`product`).",
    ])

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Done] Đã lưu báo cáo markdown tại: {output_file}")
