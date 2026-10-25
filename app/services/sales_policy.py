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
    r"\b(chưa trả|chua tra|chưa thanh toán|chua thanh toan|ghi nợ|ghi no|còn nợ|con no|nợ|"
    r"bán chịu|ban chiu|mua chịu|mua chiu|lấy chịu|lay chiu|chịu|ghi sổ|ghi so|"
    r"thiếu lại|thieu lai|còn thiếu|con thieu|thiếu|trả sau|tra sau|để sau trả|de sau tra|"
    r"pending|unpaid|credit)\b",
    re.IGNORECASE,
)


def is_unpaid_payment(raw_payment: Optional[str]) -> bool:
    text = str(raw_payment or "").strip()
    if not text:
        return False
    if _PAID_PATTERN.search(text):
        return False
    return bool(_UNPAID_PATTERN.search(text))


# =========================================================
# ĐƠN VỊ TÍNH KHI BÁN
# =========================================================
ERROR_INVALID_UNIT = "INVALID_UNIT"


def _normalize_unit(value: Optional[str]) -> str:
    import unicodedata

    text = unicodedata.normalize("NFC", str(value or "")).strip().lower()
    return re.sub(r"\s+", " ", text)


def _strip_accents(text: str) -> str:
    import unicodedata

    text = text.replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def is_unit_valid(requested_unit: Optional[str], product_unit: Optional[str]) -> bool:
    """
    Đơn vị người dùng nói phải khớp đơn vị tính của sản phẩm (Product.default_unit).
    Không nói đơn vị, hoặc sản phẩm chưa khai báo đơn vị -> hợp lệ (dùng mặc định).
    So khớp không phân biệt hoa/thường và dấu ("Lon" == "lon", "hop" == "hộp").
    """
    req = _normalize_unit(requested_unit)
    prod = _normalize_unit(product_unit)
    if not req or not prod:
        return True
    return req == prod or _strip_accents(req) == _strip_accents(prod)


def invalid_unit_message(product_name: str, requested_unit: str, product_unit: str) -> str:
    return (
        f"Đơn vị '{requested_unit}' không tồn tại cho sản phẩm '{product_name}'. "
        f"Sản phẩm này được tính theo '{product_unit}', vui lòng nói lại số lượng theo '{product_unit}'."
    )


# =========================================================
# BÁN NỢ (CREDIT SALE)
# =========================================================
_CUSTOMER_DEBT_INTENTS = ("khach_ghi_no", "ghi_no_khach_hang")


def resolve_payment(payment: Optional[str], text: Optional[str]) -> Optional[str]:
    """
    LLM không trả payment nhưng câu gốc có ý chưa trả ("bán chịu", "ghi sổ", "trả sau"...)
    -> coi là "PENDING". Có payment từ LLM thì giữ nguyên.
    """
    if str(payment or "").strip():
        return payment
    return "PENDING" if is_unpaid_payment(text) else payment


def resolve_credit_sale_intent(intent: Optional[str], entities: dict) -> tuple:
    """
    "Ghi nợ chị Lan 5 thùng bia" là bán hàng chưa thu tiền: phải đi qua ban_hang để có
    Transaction_Detail + xuất kho OUT + Debt trong cùng một transaction.
    khach_ghi_no chỉ dành cho ghi nợ tiền không kèm hàng (không trừ kho).
    Trả về (intent, entities) sau khi chuẩn hóa.
    """
    if intent in _CUSTOMER_DEBT_INTENTS and entities.get("product") and entities.get("quantity"):
        payment = entities.get("payment")
        return "ban_hang", {**entities, "payment": payment if is_unpaid_payment(payment) else "PENDING"}
    return intent, entities



# =========================================================
# TỔNG TIỀN -> ĐƠN GIÁ ("bán 5 lon hết 100k")
# =========================================================
_GOODS_INTENTS = ("ban_hang", "mua_hang", "nhap_hang")


def resolve_total_price(intent: Optional[str], entities: dict) -> dict:
    """
    LLM chỉ trích xuất total_price, backend tự tính đơn giá bằng Decimal (không để LLM làm tròn sai).
    - Nghiệp vụ hàng hóa: chưa có price, có total_price và quantity > 0 -> price = total_price / quantity.
    - Nghiệp vụ chỉ có tiền (chi_phi, thu/trả nợ...): chưa có price -> price = total_price.
    - khach_ghi_no tự xử lý total_price trong handler, giữ nguyên.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

    total = entities.get("total_price")
    if total in (None, "") or entities.get("price") not in (None, ""):
        return entities
    if intent in ("khach_ghi_no", "ghi_no_khach_hang"):
        return entities

    try:
        total_dec = Decimal(str(total))
    except (InvalidOperation, ValueError):
        return entities

    if intent in _GOODS_INTENTS:
        try:
            qty_dec = Decimal(str(entities.get("quantity")))
        except (InvalidOperation, ValueError, TypeError):
            return entities  # chưa có số lượng: validator sẽ hỏi, giữ total_price cho lượt sau
        if qty_dec <= 0:
            return entities
        price = (total_dec / qty_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {**entities, "price": float(price)}

    return {**entities, "price": float(total_dec)}
