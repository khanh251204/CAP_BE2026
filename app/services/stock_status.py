"""
Trạng thái tồn kho của một sản phẩm — cùng quy tắc với app (VoiceCashBook/src/utils/stockStatus.ts):
- OUT (Hết hàng): tồn <= 0
- LOW (Sắp hết):  0 < tồn <= mức tối thiểu
- IN  (Còn hàng): tồn > mức tối thiểu
Sản phẩm chưa cài mức tối thiểu (NULL) dùng DEFAULT_MIN_QUANTITY như app.
"""
from typing import Optional

DEFAULT_MIN_QUANTITY = 5.0

STOCK_LABELS = {"IN": "Còn hàng", "LOW": "Sắp hết", "OUT": "Hết hàng"}


def resolve_min_quantity(raw: Optional[object]) -> float:
    if raw is None:
        return DEFAULT_MIN_QUANTITY
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULT_MIN_QUANTITY


def stock_status_of(quantity: float, min_quantity: float) -> str:
    if quantity <= 0:
        return "OUT"
    if quantity <= min_quantity:
        return "LOW"
    return "IN"


def _fmt(n: float) -> str:
    """65.0 -> '65', 1250.5 -> '1.250,5' (kiểu Việt Nam)."""
    text = f"{n:,.3f}".rstrip("0").rstrip(".")
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def stock_message(name: str, quantity: float, unit: str, min_quantity: float, status: str) -> str:
    unit_text = f" {unit}" if unit else ""
    if status == "OUT":
        return f"'{name}' đã hết hàng. Bạn nên nhập thêm."
    base = f"'{name}' còn {_fmt(quantity)}{unit_text}."
    if status == "LOW":
        return f"{base} Sắp hết (mức tối thiểu {_fmt(min_quantity)}{unit_text}), nên nhập thêm."
    return base
