# app/ai/evaluation/metrics.py
# Re-export metrics from evaluation.metrics to eliminate code duplication.

from evaluation.metrics import (
    remove_vietnamese_accents,
    normalize_intent,
    normalize_unit,
    normalize_product_name,
    is_match_price,
    is_match_text,
    calculate_classification_metrics,
    calculate_entity_metrics,
)

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
