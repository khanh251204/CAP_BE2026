from typing import List, Dict, Any, Optional
import pandas as pd
from sklearn.metrics import confusion_matrix


def generate_confusion_matrix(
    y_true: List[str],
    y_pred: List[str],
    labels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Tạo ma trận nhầm lẫn (Confusion Matrix) dùng scikit-learn.
    Trả về DataFrame và dictionary representation.
    """
    if not labels:
        labels = sorted(list(set(y_true) | set(y_pred)))

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    df_cm = pd.DataFrame(cm, index=[f"true_{l}" for l in labels], columns=[f"pred_{l}" for l in labels])

    return {
        "labels": labels,
        "matrix": cm.tolist(),
        "dataframe": df_cm
    }


def save_confusion_matrix_csv(df_cm: pd.DataFrame, output_path: str):
    """Lưu Confusion Matrix ra file CSV."""
    df_cm.to_csv(output_path, index=True, encoding="utf-8")


def format_confusion_matrix_markdown(df_cm: pd.DataFrame) -> str:
    """Định dạng Confusion Matrix dưới dạng bảng Markdown."""
    lines = []
    headers = ["True \\ Pred"] + list(df_cm.columns)
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join([":---"] + [":---:" for _ in df_cm.columns]) + " |")

    for idx, row in df_cm.iterrows():
        row_vals = [str(idx)] + [str(v) for v in row.values]
        lines.append("| " + " | ".join(row_vals) + " |")

    return "\n".join(lines)
