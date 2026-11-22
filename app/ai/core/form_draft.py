"""Nhập giao dịch bằng biểu mẫu: dựng entities + câu mô tả để dùng chung luồng bản nháp với giọng nói."""
from typing import Optional

FORM_INTENTS = {
    "ban_hang": "Bán",
    "mua_hang": "Nhập",
    "chi_phi": "Chi",
    "khach_ghi_no": "Ghi nợ khách",
    "thu_no_khach": "Thu nợ",
    "ghi_no_nha_cung_cap": "Ghi nợ nhà cung cấp",
    "tra_no_nha_cung_cap": "Trả nợ nhà cung cấp",
}

_PAYMENT_TEXT = {
    "cash": "tiền mặt",
    "transfer": "chuyển khoản",
    "card": "thẻ",
    "debt": "chưa trả",
}
_PAYMENT_PHRASE = {"cash": "tiền mặt", "transfer": "chuyển khoản", "card": "quẹt thẻ", "debt": "ghi nợ"}


def _num(v: Optional[float]) -> str:
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else str(v)


def build_entities(body) -> dict:
    """Chỉ giữ các trường có giá trị. `payment` đổi sang chữ mà handler hiểu."""
    e = {
        "product": body.product,
        "product_id": body.product_id,
        "quantity": body.quantity,
        "unit": body.unit,
        "price": body.price,
        "total_price": body.total_price,
        "customer": body.customer,
        "customer_id": body.customer_id,
        "supplier": body.supplier,
        "supplier_id": body.supplier_id,
        "category": body.category,
        "note": body.note,
        "date": body.date,
        "payment": _PAYMENT_TEXT.get(body.payment or ""),
    }
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in e.items() if v not in (None, "")}


def describe(body) -> str:
    """Câu tiếng Việt mô tả giao dịch, hiện ở ô "Nội dung" của màn Xác nhận và lưu làm input_text."""
    verb = FORM_INTENTS.get(body.intent, "Giao dịch")
    parts = [verb]
    if body.quantity:
        parts.append(f"{_num(body.quantity)} {body.unit or ''}".strip())
    if body.product:
        parts.append(body.product)
    if body.category:
        parts.append(body.category)
    who = body.customer or body.supplier
    if who:
        parts.append(who)
    if body.total_price:
        parts.append(f"{_num(body.total_price)}đ")
    elif body.price:
        parts.append(f"giá {_num(body.price)}đ" if body.quantity else f"{_num(body.price)}đ")
    pay = _PAYMENT_PHRASE.get(body.payment or "")
    if pay:
        parts.append(pay)
    return " ".join(p for p in parts if p).strip()
