"""
Quy tắc bán hàng theo business_type & product_type (xem AGENTS.md mục 3).

Dùng chung cho bước tạo bản nháp (ban_hang handler) và bước xác nhận (InventoryService.sell_goods)
để hai nơi không bao giờ lệch nhau.
"""
import re
from typing import Optional

from sqlalchemy.orm import Session


# Chính sách tồn kho khi bán
STRICT = "STRICT"                        # Bắt buộc đủ tồn kho, trừ kho OUT
MADE_TO_ORDER = "MADE_TO_ORDER"          # Cho phép bán khi thiếu kho, chỉ trừ phần đang có (không âm kho)
NO_INVENTORY = "NO_INVENTORY"            # Dịch vụ: không kiểm tra, không tạo OUT
RAW_MATERIAL_BLOCKED = "RAW_MATERIAL_BLOCKED"  # Nguyên liệu: không được bán trực tiếp

ERROR_INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
ERROR_CANNOT_SELL_RAW_MATERIAL = "cannot_sell_raw_material"

DEFAULT_BUSINESS_TYPE = "RESELLER"
DEFAULT_PRODUCT_TYPE = "RESALE"


def normalize_business_type(value: Optional[str]) -> str:
    v = str(value or "").strip().upper()
    return v if v in ("RESELLER", "PRODUCER", "SERVICE") else DEFAULT_BUSINESS_TYPE


def normalize_product_type(value: Optional[str]) -> str:
    v = str(getattr(value, "value", value) or "").strip().upper()
    return v if v in ("RESALE", "RAW_MATERIAL", "FINISHED_GOOD") else DEFAULT_PRODUCT_TYPE


def get_sale_stock_policy(business_type: Optional[str], product_type: Optional[str]) -> str:
    bt = normalize_business_type(business_type)
    pt = normalize_product_type(product_type)

    if bt == "SERVICE":
        return NO_INVENTORY
    if bt == "PRODUCER":
        if pt == "RAW_MATERIAL":
            return RAW_MATERIAL_BLOCKED
        if pt == "FINISHED_GOOD":
            return MADE_TO_ORDER
    return STRICT


def get_user_business_type(db: Session, user_id: int) -> str:
    from app.models.user_model import User

    row = db.query(User.business_type).filter(User.user_id == user_id).first()
    return normalize_business_type(row[0] if row else None)


# "chưa trả", "ghi nợ", "còn nợ"... -> chưa thanh toán. So khớp theo từ, không theo chuỗi con
# để tránh các trường hợp như "KHÔNG NỢ" hay chuỗi bất kỳ có chứa "NO".
_PAID_PATTERN = re.compile(
    r"\b(không nợ|khong no|đã trả|da tra|đã thanh toán|da thanh toan|paid)\b",
    re.IGNORECASE,
)
_UNPAID_PATTERN = re.compile(
    r"\b(chưa trả|chua tra|chưa thanh toán|chua thanh toan|ghi nợ|ghi no|còn nợ|con no|nợ|pending|unpaid)\b",
    re.IGNORECASE,
)


def is_unpaid_payment(raw_payment: Optional[str]) -> bool:
    text = str(raw_payment or "").strip()
    if not text:
        return False
    if _PAID_PATTERN.search(text):
        return False
    return bool(_UNPAID_PATTERN.search(text))
