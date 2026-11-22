import re
from typing import Any, Optional

from app.ai.intents.missing_info import _NUMBER

# Câu hỏi tồn kho ("coca còn 15 lon không", "còn bao nhiêu") -> chỉ tra cứu, không kiểm kê
_QUESTION = re.compile(
    r"\?|\b(?:bao nhiêu|mấy|không|ko|hông|chưa|hả|nhỉ|đủ không)\s*[?.!]*\s*$|\bbao nhiêu\b",
    re.IGNORECASE,
)


def counted_quantity(entities: dict[str, Any], text: str) -> Optional[float]:
    """
    Số đếm thực tế người dùng báo khi kiểm kho, hoặc None nếu chỉ hỏi tồn.
    Chỉ nhận khi câu thật sự có số nằm SAU tên sản phẩm và câu không phải câu hỏi,
    để quantity do LLM tự đoán không biến câu hỏi thành lệnh sửa tồn kho.
    """
    qty = entities.get("quantity")
    if qty is None or (isinstance(qty, str) and not qty.strip()):
        return None
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return None

    t = (text or "").lower().strip()
    if not t or _QUESTION.search(t):
        return None
    product = str(entities.get("product") or "").lower().strip()
    idx = t.find(product) if product else -1
    after = t[idx + len(product):] if idx >= 0 else t
    if not re.search(_NUMBER, after):
        return None
    return qty


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của kiem_kho thành payload chuẩn.
    Kiểm kê: `quantity` là số đếm thực tế.
    """
    return {
        "product_name": entities.get("product"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "input_text": text,
    }
