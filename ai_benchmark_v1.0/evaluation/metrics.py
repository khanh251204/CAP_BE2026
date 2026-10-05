# evaluation/metrics.py
import re
from typing import Dict, List, Any, Optional
from collections import defaultdict

from evaluation.normalization_helpers import (
    remove_vietnamese_accents,
    normalize_intent,
    normalize_unit,
    normalize_product_name,
)


def is_match_price(pred_price: Any, true_price: Any, quantity: Any = None) -> bool:
    """
    So sánh giá trị tiền/đơn giá:
    - Trực tiếp: pred_price == true_price
    - Hoặc quan hệ tổng tiền vs đơn giá: true_price = pred_price * quantity
    """
    try:
        if pred_price is None or true_price is None:
            return False
        p_pred = float(pred_price)
        p_true = float(true_price)
        if abs(p_pred - p_true) < 1.0:
            return True
        if quantity:
            q = float(quantity)
            if q > 0 and abs(p_pred * q - p_true) < 1.0:
                return True
            if q > 0 and abs(p_true * q - p_pred) < 1.0:
                return True
        return False
    except (ValueError, TypeError):
        return False


def is_match_text(pred_str: Any, true_str: Any) -> bool:
    """So sánh chuỗi văn bản (tên sản phẩm, khách hàng, ncc, thời gian...)"""
    if pred_str is None or true_str is None:
        return False
    s1 = remove_vietnamese_accents(str(pred_str)).strip()
    s2 = remove_vietnamese_accents(str(true_str)).strip()
    if not s1 or not s2:
        return False
    return s1 == s2 or s1 in s2 or s2 in s1


def calculate_classification_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
    """
    Tính toán các chỉ số phân loại (Intent / Type):
    - Accuracy
    - Precision, Recall, F1-score (Macro, Micro, Weighted, Per-class)
    """
    total = len(y_true)
    if total == 0:
        return {
            "accuracy": 0.0,
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "per_class": {}
        }

    classes = sorted(list(set(y_true) | set(y_pred)))
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    support = defaultdict(int)
    correct = 0

    for yt, yp in zip(y_true, y_pred):
        support[yt] += 1
        if yt == yp:
            correct += 1
            tp[yt] += 1
        else:
            fp[yp] += 1
            fn[yt] += 1

    accuracy = correct / total
    per_class = {}
    macro_p_sum = 0.0
    macro_r_sum = 0.0
    macro_f1_sum = 0.0
    weighted_f1_sum = 0.0

    for c in classes:
        c_tp = tp[c]
        c_fp = fp[c]
        c_fn = fn[c]
        c_sup = support[c]

        precision = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0.0
        recall = c_tp / (c_tp + c_fn) if (c_tp + c_fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[c] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": c_sup
        }

        macro_p_sum += precision
        macro_r_sum += recall
        macro_f1_sum += f1
        weighted_f1_sum += f1 * c_sup

    num_classes = len(classes) if classes else 1
    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_p_sum / num_classes, 4),
        "macro_recall": round(macro_r_sum / num_classes, 4),
        "macro_f1": round(macro_f1_sum / num_classes, 4),
        "weighted_f1": round(weighted_f1_sum / total, 4) if total > 0 else 0.0,
        "total_samples": total,
        "per_class": per_class
    }


def calculate_entity_metrics(
    true_entities_list: List[Dict[str, Any]],
    pred_entities_list: List[Dict[str, Any]],
    entity_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Tính Precision, Recall, F1 cho bài toán trích xuất thực thể (Slot Filling / NER).
    Hỗ trợ từng thực thể: product, price, quantity, unit, customer, supplier, date.
    """
    if entity_keys is None:
        entity_keys = ["product", "price", "quantity", "unit", "customer", "supplier", "date"]

    stats = {k: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for k in entity_keys}

    for true_ents, pred_ents in zip(true_entities_list, pred_entities_list):
        for key in entity_keys:
            t_val = true_ents.get(key)
            p_val = pred_ents.get(key)

            t_has = t_val is not None and str(t_val).strip() != "" and str(t_val) != "nan"
            p_has = p_val is not None and str(p_val).strip() != "" and str(p_val) != "None" and str(p_val) != "nan"

            if t_has:
                stats[key]["support"] += 1

            if t_has and p_has:
                match = False
                if key == "price":
                    match = is_match_price(p_val, t_val, true_ents.get("quantity") or pred_ents.get("quantity"))
                elif key == "quantity":
                    try:
                        match = float(p_val) == float(t_val)
                    except (ValueError, TypeError):
                        match = False
                elif key == "unit":
                    match = normalize_unit(p_val) == normalize_unit(t_val)
                else:
                    match = is_match_text(p_val, t_val)

                if match:
                    stats[key]["tp"] += 1
                else:
                    stats[key]["fp"] += 1
                    stats[key]["fn"] += 1
            elif t_has and not p_has:
                stats[key]["fn"] += 1
            elif not t_has and p_has:
                stats[key]["fp"] += 1

    per_entity = {}
    total_tp = total_fp = total_fn = total_support = 0
    macro_p_sum = macro_r_sum = macro_f1_sum = 0.0
    active_keys_count = 0

    for key in entity_keys:
        tp = stats[key]["tp"]
        fp = stats[key]["fp"]
        fn = stats[key]["fn"]
        sup = stats[key]["support"]

        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_support += sup

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

        per_entity[key] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "support": sup,
            "tp": tp,
            "fp": fp,
            "fn": fn
        }

        if sup > 0 or (tp + fp) > 0:
            macro_p_sum += p
            macro_r_sum += r
            macro_f1_sum += f1
            active_keys_count += 1

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)) if (micro_p + micro_r) > 0 else 0.0

    k_div = active_keys_count if active_keys_count > 0 else 1
    return {
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_precision": round(macro_p_sum / k_div, 4),
        "macro_recall": round(macro_r_sum / k_div, 4),
        "macro_f1": round(macro_f1_sum / k_div, 4),
        "total_support": total_support,
        "per_entity": per_entity
    }


__all__ = [
    "remove_vietnamese_accents",
    "normalize_intent",
    "normalize_unit",
    "normalize_product_name",
    "is_match_price",
    "is_match_text",
    "calculate_classification_metrics",
    "calculate_entity_metrics",
]
