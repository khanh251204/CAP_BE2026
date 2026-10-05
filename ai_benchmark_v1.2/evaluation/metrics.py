from typing import Dict, List, Any, Optional
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from ai_benchmark.evaluation.normalization import (
    normalize_intent,
    is_entity_match_strict,
    is_entity_match_normalized
)

ENTITY_FIELDS = [
    "product",
    "new_product_name",
    "price",
    "quantity",
    "unit",
    "customer",
    "supplier",
    "date",
    "payment"
]


def calculate_intent_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
    """
    Tính toán chỉ số Intent Classification bằng scikit-learn:
    - Accuracy
    - Macro Precision, Recall, F1
    - Weighted Precision, Recall, F1
    - Per-class breakdown
    """
    if not y_true:
        return {}

    acc = accuracy_score(y_true, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )

    # Chi tiết từng nhãn
    report_dict = classification_report(
        y_true, y_pred, output_dict=True, zero_division=0
    )

    per_class = {}
    for key, val in report_dict.items():
        if key not in ("accuracy", "macro avg", "weighted avg") and isinstance(val, dict):
            per_class[key] = {
                "precision": round(val["precision"], 4),
                "recall": round(val["recall"], 4),
                "f1": round(val["f1-score"], 4),
                "support": int(val["support"])
            }

    return {
        "accuracy": round(acc, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_precision": round(weighted_p, 4),
        "weighted_recall": round(weighted_r, 4),
        "weighted_f1": round(weighted_f1, 4),
        "total_samples": len(y_true),
        "per_class": per_class
    }


def calculate_entity_metrics(
    true_entities_list: List[Dict[str, Any]],
    pred_entities_list: List[Dict[str, Any]],
    fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Tính Precision, Recall, F1 cho 9 thực thể (Slot Filling).
    Tính cả Micro & Macro averages.
    """
    if fields is None:
        fields = ENTITY_FIELDS

    stats = {k: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for k in fields}

    for t_dict, p_dict in zip(true_entities_list, pred_entities_list):
        for key in fields:
            t_val = t_dict.get(key)
            p_val = p_dict.get(key) if p_dict else None

            # Bỏ qua giá trị rỗng/nan của ground truth
            t_has = t_val is not None and str(t_val).strip() != "" and str(t_val).lower() not in ("nan", "none")
            p_has = p_val is not None and str(p_val).strip() != "" and str(p_val).lower() not in ("nan", "none")

            if t_has:
                stats[key]["support"] += 1

            if t_has and p_has:
                matched = is_entity_match_normalized(
                    key, p_val, t_val, quantity=t_dict.get("quantity") or (p_dict.get("quantity") if p_dict else None)
                )
                if matched:
                    stats[key]["tp"] += 1
                else:
                    stats[key]["fp"] += 1
                    stats[key]["fn"] += 1
            elif t_has and not p_has:
                stats[key]["fn"] += 1
            elif not t_has and p_has:
                stats[key]["fp"] += 1

    per_entity = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_sup = 0

    macro_p_sum = 0.0
    macro_r_sum = 0.0
    macro_f1_sum = 0.0
    active_keys = 0

    for key in fields:
        tp = stats[key]["tp"]
        fp = stats[key]["fp"]
        fn = stats[key]["fn"]
        sup = stats[key]["support"]

        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_sup += sup

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

        per_entity[key] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": sup
        }

        if sup > 0 or (tp + fp) > 0:
            macro_p_sum += p
            macro_r_sum += r
            macro_f1_sum += f1
            active_keys += 1

    div = active_keys if active_keys > 0 else 1
    macro_p = macro_p_sum / div
    macro_r = macro_r_sum / div
    macro_f1 = macro_f1_sum / div

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)) if (micro_p + micro_r) > 0 else 0.0

    return {
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "total_support": total_sup,
        "per_entity": per_entity
    }


def calculate_end_to_end_metrics(
    y_true_intent: List[str],
    y_pred_intent: List[str],
    true_entities_list: List[Dict[str, Any]],
    pred_entities_list: List[Dict[str, Any]],
    fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Tính End-to-End Accuracy:
    - Strict Match: raw intent == pred intent AND mọi entity ground truth khớp chính xác (strict equality)
    - Normalized Match: normalized intent khớp AND mọi entity ground truth khớp normalized
    """
    if fields is None:
        fields = ENTITY_FIELDS

    total = len(y_true_intent)
    if total == 0:
        return {"strict_match_accuracy": 0.0, "normalized_match_accuracy": 0.0, "total": 0}

    strict_correct = 0
    norm_correct = 0

    for yt_raw, yp_raw, t_ents, p_ents in zip(y_true_intent, y_pred_intent, true_entities_list, pred_entities_list):
        if p_ents is None:
            p_ents = {}

        # 1. Strict Match check
        strict_intent = (str(yt_raw).strip() == str(yp_raw).strip())
        strict_ents = True
        for key in fields:
            tv = t_ents.get(key)
            # Chỉ yêu cầu các entity có mặt trong ground truth
            if tv is not None and str(tv).strip() != "" and str(tv).lower() not in ("nan", "none"):
                pv = p_ents.get(key)
                if not is_entity_match_strict(pv, tv):
                    strict_ents = False
                    break
        if strict_intent and strict_ents:
            strict_correct += 1

        # 2. Normalized Match check
        norm_intent = (normalize_intent(yt_raw) == normalize_intent(yp_raw))
        norm_ents = True
        for key in fields:
            tv = t_ents.get(key)
            if tv is not None and str(tv).strip() != "" and str(tv).lower() not in ("nan", "none"):
                pv = p_ents.get(key)
                matched = is_entity_match_normalized(
                    key, pv, tv, quantity=t_ents.get("quantity") or p_ents.get("quantity")
                )
                if not matched:
                    norm_ents = False
                    break
        if norm_intent and norm_ents:
            norm_correct += 1

    return {
        "total_samples": total,
        "strict_match_count": strict_correct,
        "strict_match_accuracy": round(strict_correct / total, 4),
        "normalized_match_count": norm_correct,
        "normalized_match_accuracy": round(norm_correct / total, 4)
    }
