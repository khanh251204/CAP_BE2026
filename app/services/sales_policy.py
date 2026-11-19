"""
Quy tắc bán hàng theo business_type & product_type (xem AGENTS.md mục 3).

Dùng chung cho bước tạo bản nháp (ban_hang handler) và bước xác nhận (InventoryService.sell_goods)
để hai nơi không bao giờ lệch nhau.
"""
import re
from typing import Any, Optional

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


# Cụm từ chắc chắn là CHƯA TRẢ TIỀN: câu có cụm này thì là ghi nợ, kể cả khi LLM ghi "tiền mặt".
# (Không gồm "nợ" / "thiếu" đứng riêng: "bán 5 lon, thiếu 1 lon" không phải ghi nợ.)
_STRONG_UNPAID = re.compile(
    r"(chưa trả|chua tra|chưa thanh toán|chua thanh toan|chưa đưa tiền|chua dua tien|"
    r"ghi nợ|ghi no|bán nợ|ban no|mua nợ|mua no|nhập nợ|nhap no|lấy nợ|lay no|còn nợ|con no|"
    r"bán chịu|ban chiu|mua chịu|mua chiu|lấy chịu|lay chiu|nhập chịu|nhap chiu|ghi sổ|ghi so|"
    r"trả sau|tra sau|để sau trả|de sau tra)",
    re.IGNORECASE,
)


def resolve_payment(payment: Optional[str], text: Optional[str]) -> Optional[str]:
    """
    Trạng thái thanh toán của bán / nhập hàng:
    - Câu gốc có cụm chưa trả tiền ("chưa trả tiền", "ghi nợ", "bán chịu", "trả sau"...) -> "PENDING".
    - LLM ghi payment là chữ chưa trả ("chưa trả tiền", "nợ") -> chuẩn hóa thành "PENDING".
    - LLM bỏ trống payment, câu có ý chưa trả theo mẫu rộng ("bán chịu", "thiếu lại"...) -> "PENDING".
    - Còn lại giữ payment của LLM.
    """
    raw_text = str(text or "")
    if _STRONG_UNPAID.search(raw_text) and not _PAID_PATTERN.search(raw_text):
        return "PENDING"
    if is_unpaid_payment(payment):
        return "PENDING"
    if str(payment or "").strip():
        return payment
    return "PENDING" if is_unpaid_payment(raw_text) else payment


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


def order_total(total_price: Any, unit_price: Any, quantity: Any) -> Optional[float]:
    """
    Tổng tiền đơn hàng: người dùng nói tổng ("2 lốc 50k") thì giữ đúng số đó
    (tránh 3 x 16.666,67 = 50.000,01); không thì = số lượng x đơn giá (Decimal).
    """
    from decimal import Decimal, InvalidOperation

    try:
        if total_price not in (None, ""):
            return float(Decimal(str(total_price)))
        if unit_price in (None, "") or quantity in (None, ""):
            return None
        return float(Decimal(str(unit_price)) * Decimal(str(quantity)))
    except (InvalidOperation, ValueError, TypeError):
        return None


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

    # Có hàng + số lượng (kể cả ghi nợ NCC "ghi nợ NCC A 2 lốc sữa chua 50k") -> total là tiền cả đơn
    has_goods = bool(entities.get("product")) and entities.get("quantity") not in (None, "")
    if intent in _GOODS_INTENTS or has_goods:
        try:
            qty_dec = Decimal(str(entities.get("quantity")))
        except (InvalidOperation, ValueError, TypeError):
            return entities  # chưa có số lượng: validator sẽ hỏi, giữ total_price cho lượt sau
        if qty_dec <= 0:
            return entities
        price = (total_dec / qty_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {**entities, "price": float(price)}

    return {**entities, "price": float(total_dec)}


# =========================================================
# TRẢ TRƯỚC MỘT PHẦN ("mới trả 20k", "đưa trước 200k còn lại ghi nợ", "trả một nửa")
# =========================================================
# LLM nhận ra payment = "PARTIAL" nhưng không trả số tiền đã trả -> đơn bị ghi là trả đủ, không có nợ.
# Đọc số tiền / tỉ lệ đã trả từ câu gốc (đã chuẩn hóa tiền: "20k" -> "20000 đồng").
_PAY_VERB = (
    r"(?:trả|tra|đưa|dua|thanh toán|thanh toan|gửi|gui|chuyển khoản|chuyen khoan|chuyển|chuyen|"
    r"đặt cọc|dat coc|cọc|coc)"
)
# Từ đệm giữa động từ và số tiền: "đưa trước", "trả được", "trả cho tôi", "chuyển khoản trước"...
_PAY_FILLER = (
    r"(?:\s+(?:trước|truoc|được|duoc|có|co|mới|moi|rồi|roi|tiền|tien|khoảng|khoang|là|la|"
    r"cho\s+(?:tôi|toi|tui|em|mình|minh|anh|chị|chi|cô|co|chú|chu)))*"
)
_PAID_MONEY = re.compile(
    r"(?<!\w)" + _PAY_VERB + _PAY_FILLER
    + r"\s+(\d[\d.,]*)\s*(k|nghìn|nghin|ngàn|ngan|triệu|trieu|tr|đồng|dong|đ|vnđ|vnd)?(?![\w/%])",
    re.IGNORECASE,
)
_PAID_HALF = re.compile(r"(?<!\w)" + _PAY_VERB + _PAY_FILLER + r"\s+(?:(?:một|mot|1)\s+)?(?:nửa|nua)(?!\w)", re.IGNORECASE)
_PAID_FRACTION = re.compile(r"(?<!\w)" + _PAY_VERB + _PAY_FILLER + r"\s+1\s*/\s*([2-9])(?![\d.,])", re.IGNORECASE)
_PAID_PERCENT = re.compile(r"(?<!\w)" + _PAY_VERB + _PAY_FILLER + r"\s+(\d{1,3})\s*(?:%|phần trăm|phan tram)", re.IGNORECASE)
_MONEY_SCALE = {"k": 1000, "nghìn": 1000, "nghin": 1000, "ngàn": 1000, "ngan": 1000,
                "triệu": 1_000_000, "trieu": 1_000_000, "tr": 1_000_000}


def _money_value(raw: str, suffix: Optional[str]) -> Optional[float]:
    raw = raw.rstrip(".,")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
        raw = re.sub(r"[.,]", "", raw)  # 50.000 / 1,200,000 là phân cách hàng nghìn
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return None
    scale = _MONEY_SCALE.get(str(suffix or "").lower())
    if scale:
        return value * scale
    # Không có chữ tiền: số nhỏ là số lượng hàng ("đưa 2 thùng"), không phải tiền
    return value if suffix or value >= 1000 else None


def resolve_amount_paid(intent: Optional[str], entities: dict, text: Optional[str]) -> dict:
    """
    Bán / mua / nhập hàng có trả trước một phần:
    - "mới trả 20000 đồng", "đưa trước 200k" -> amount_paid = số tiền đó.
    - "trả một nửa", "trả 1/2", "trả trước 30%" -> amount_paid_ratio (handler nhân với tổng tiền đơn,
      vì đơn giá có thể lấy từ danh mục, ở bước này chưa biết tổng).
    Đã có amount_paid thì giữ nguyên.
    """
    if intent not in _GOODS_INTENTS or not isinstance(entities, dict):
        return entities
    if entities.get("amount_paid") not in (None, ""):
        return entities
    raw = str(text or "")
    for m in _PAID_MONEY.finditer(raw):
        value = _money_value(m.group(1), m.group(2))
        if value is not None and value > 0:
            return {**entities, "amount_paid": value}
    ratio = None
    if _PAID_HALF.search(raw):
        ratio = 0.5
    elif (m := _PAID_FRACTION.search(raw)):
        ratio = 1 / int(m.group(1))
    elif (m := _PAID_PERCENT.search(raw)) and 0 < int(m.group(1)) <= 100:
        ratio = int(m.group(1)) / 100
    return {**entities, "amount_paid_ratio": ratio} if ratio else entities


def resolve_order_paid(entities: dict, total_amount: Optional[float]) -> Optional[float]:
    """
    Số tiền đã trả của đơn (None = không nói): amount_paid, hoặc tỉ lệ x tổng tiền.
    Không vượt tổng tiền ("đưa 100k" cho đơn 84k là khách đưa dư, không phải trả 100k).
    """
    paid: Any = entities.get("amount_paid")
    if paid in (None, ""):
        ratio = entities.get("amount_paid_ratio")
        if ratio in (None, "") or total_amount is None:
            return None
        try:
            paid = round(float(total_amount) * float(ratio))
        except (TypeError, ValueError):
            return None
    try:
        paid = float(paid)
    except (TypeError, ValueError):
        paid = 0.0
    if total_amount is not None and paid > float(total_amount):
        paid = float(total_amount)
    return paid


def is_partial_payment(raw_payment: Optional[str]) -> bool:
    """LLM ghi "PARTIAL" / "trả một phần" nhưng không có số tiền đã trả -> phải hỏi lại."""
    text = str(raw_payment or "").strip().lower()
    return text in ("partial", "trả một phần", "tra mot phan", "một phần", "mot phan", "trả bớt", "tra bot")
