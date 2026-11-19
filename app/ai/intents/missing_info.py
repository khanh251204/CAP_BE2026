"""
Câu nhắc khi người dùng nói thiếu thông tin — dùng chung cho mọi intent.
Luôn là tiếng Việt, nói rõ thiếu gì và kèm ví dụ. Không dùng câu do LLM tự viết.
"""
import re
from typing import Any, Iterable, Optional

FIELD_LABELS = {
    "product": "tên sản phẩm",
    "quantity": "số lượng",
    "unit": "đơn vị tính",
    "price": "giá",
    "total_price": "số tiền",
    "amount": "số tiền",
    "customer": "tên khách hàng",
    "supplier": "tên nhà cung cấp",
}


def _is_empty(val: Any) -> bool:
    return val is None or (isinstance(val, str) and not val.strip())


def first_value(*values: Any) -> Any:
    """Giá trị đầu tiên người dùng có nói (kể cả 0). Khác `a or b`: `0 or None` làm mất số 0."""
    return next((v for v in values if not _is_empty(v)), None)


def is_not_positive(value: Any) -> bool:
    """Có nói số tiền nhưng <= 0 (hoặc không phải số) → phải báo "phải lớn hơn 0"."""
    if _is_empty(value):
        return False
    try:
        return float(value) <= 0
    except (ValueError, TypeError):
        return True


def missing_message(
    missing_fields: Iterable[str],
    example: Optional[str] = None,
    labels: Optional[dict] = None,
) -> str:
    names = {**FIELD_LABELS, **(labels or {})}
    parts = list(dict.fromkeys(names.get(f, f) for f in missing_fields))
    text = f"Bạn chưa nói {', '.join(parts)}." if parts else "Câu lệnh còn thiếu thông tin."
    return f"{text} Ví dụ: \"{example}\"." if example else text


def check_required(
    entities: dict,
    required: Iterable[str],
    example: Optional[str] = None,
    labels: Optional[dict] = None,
    alternatives: Optional[dict] = None,
) -> dict:
    """
    Kiểm tra các trường bắt buộc. `alternatives` cho phép một trường được thay bằng trường khác,
    vd: {"price": ("amount", "total_price")} — đã nói tổng tiền thì không hỏi lại giá.
    """
    alternatives = alternatives or {}
    missing = [
        f for f in required
        if _is_empty(entities.get(f))
        and all(_is_empty(entities.get(a)) for a in alternatives.get(f, ()))
    ]
    if missing:
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": missing,
            "message": missing_message(missing, example, labels),
        }
    return {"success": True, "missing_fields": []}


# ---------------------------------------------------------------------------
# Số lượng do LLM tự đoán
# ---------------------------------------------------------------------------
# LLM hay tự điền quantity=1 khi người dùng không nói số lượng
# (vd "Bán lốc sữa chua 50000, tiền mặt" -> quantity=1). Backend kiểm tra lại trên câu gốc.

# Intent có hàng hóa + số lượng bắt buộc
QUANTITY_INTENTS = {"ban_hang", "mua_hang", "nhap_hang", "nhap_kho", "xuat_kho", "hang_hong"}

# Số đọc bằng chữ (bước chuẩn hóa không đổi sang chữ số). "vài", "mấy" không phải số lượng cụ thể.
_NUMBER_WORDS = (
    "một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|chục|trăm|nửa|rưỡi|đôi|cặp|tá"
)
_NUMBER = rf"(?:\d+(?:[.,]\d+)?|\b(?:{_NUMBER_WORDS})\b)"


def quantity_was_spoken(text: str, product: Any, unit: Any = None) -> Optional[bool]:
    """
    Người dùng có nói số lượng không. Số lượng đứng trước tên sản phẩm ("bán 2 lốc sữa chua")
    hoặc ngay trước đơn vị phía sau tên ("bán sữa chua 2 lốc").
    Trả về None nếu không tìm thấy tên sản phẩm trong câu (không đủ căn cứ để kết luận).
    """
    if _is_empty(text) or _is_empty(product):
        return None
    t = str(text).lower()
    p = str(product).lower().strip()
    idx = t.find(p)
    if idx < 0:
        return None
    if re.search(_NUMBER, t[:idx]):
        return True
    if not _is_empty(unit):
        after = t[idx + len(p):]
        if re.search(rf"{_NUMBER}\s*{re.escape(str(unit).lower().strip())}\b", after):
            return True
    return False


def drop_unspoken_quantity(intent: Optional[str], entities: dict, text: str) -> dict:
    """Bỏ quantity LLM tự đoán để validator hỏi lại người dùng."""
    if intent not in QUANTITY_INTENTS or _is_empty(entities.get("quantity")):
        return entities
    if quantity_was_spoken(text, entities.get("product"), entities.get("unit")) is False:
        return {**entities, "quantity": None}
    return entities


# ---------------------------------------------------------------------------
# Số âm LLM bỏ dấu
# ---------------------------------------------------------------------------
# "Thanh toán tiền điện -1000000" -> LLM trả price=1000000 (mất dấu âm) -> validator không chặn được.
# Tìm số âm trong câu ("-1000000", "-1.000.000", "âm 500000") rồi gắn lại dấu cho trường tương ứng,
# để validator của từng intent báo "phải lớn hơn 0".
# Chỉ nhận "-" dính liền số và đứng đầu câu / sau khoảng trắng: "ngày 10-11" không phải số âm.
_NEGATIVE = re.compile(r"(?:(?<=\s)|^)(?:[-−–]|âm\s+)(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)", re.IGNORECASE)
_NUMERIC_FIELDS = ("price", "total_price", "amount", "unit_price", "original_amount", "amount_paid", "quantity")


def _parse_number(raw: str) -> Optional[float]:
    # "1.000.000" / "1,000,000" là phân cách hàng nghìn; "1,5" là thập phân
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
        raw = re.sub(r"[.,]", "", raw)
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def restore_negative_numbers(entities: dict, text: str) -> dict:
    if _is_empty(text):
        return entities
    negatives = {v for v in (_parse_number(m) for m in _NEGATIVE.findall(str(text))) if v}
    if not negatives:
        return entities
    fixed = dict(entities)
    for field in _NUMERIC_FIELDS:
        try:
            value = float(fixed.get(field))
        except (TypeError, ValueError):
            continue
        if value > 0 and value in negatives:
            fixed[field] = -value
    return fixed

# ---------------------------------------------------------------------------
# Số tiền LLM bỏ trống
# ---------------------------------------------------------------------------
# Nghiệp vụ chỉ có tiền (thu / trả / ghi nợ, chi phí): LLM đôi khi nhận đúng intent và tên người
# nhưng để price = null ("thu nợ 20000000 từ Mai" -> price=null) -> người dùng bị hỏi lại số tiền đã nói.
# Câu có ĐÚNG MỘT số tiền thì lấy số đó. Số âm GIỮ NGUYÊN dấu (không đổi thành dương)
# để handler cảnh báo "phải lớn hơn 0". Số 0 không điền (để validator xử lý như thiếu số tiền).
MONEY_ONLY_INTENTS = {
    "chi_phi", "chi_tien",
    "khach_ghi_no", "ghi_no_khach_hang",
    "thu_no_khach", "thu_no_khach_hang",
    "ghi_no_nha_cung_cap",
    "tra_no_nha_cung_cap",
}
_AMOUNT_FIELDS = ("price", "amount", "total_price")
_AMOUNT = re.compile(
    r"(?<![\w.,\-−–])((?:[-−–]|âm\s+)?)(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?![\d.,]*\d)",
    re.IGNORECASE,
)


def fill_missing_amount(intent: Optional[str], entities: dict, text: str) -> dict:
    """Điền price từ câu gốc khi LLM bỏ trống. Không đoán khi câu có nhiều số hoặc có hàng hóa."""
    if intent not in MONEY_ONLY_INTENTS or not isinstance(entities, dict) or _is_empty(text):
        return entities
    if any(not _is_empty(entities.get(f)) for f in _AMOUNT_FIELDS):
        return entities
    if not _is_empty(entities.get("product")) or not _is_empty(entities.get("quantity")):
        return entities
    values = set()
    for sign, raw in _AMOUNT.findall(str(text)):
        value = _parse_number(raw)
        if value is None:
            continue
        values.add(-value if sign else value)
    if len(values) != 1:
        return entities
    value = values.pop()
    if value == 0:
        return entities
    return {**entities, "price": int(value) if float(value).is_integer() else value}
