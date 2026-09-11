from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của chi_phi thành payload chuẩn.
    """
    amount = entities.get("price") or entities.get("amount") or entities.get("total_price")
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        amount = 0.0

    category = entities.get("category") or entities.get("category_name")
    if not category and text:
        text_lower = text.lower()
        for kw in ["tiền điện", "tiền nước", "mặt bằng", "tiền nhà", "thuê nhà", "vận chuyển", "tiền ship", "xăng xe", "văn phòng phẩm"]:
            if kw in text_lower:
                category = kw.capitalize()
                break

    note = entities.get("note") or category or "Chi phí"

    return {
        "amount": amount,
        "category": category,
        "category_name": category,
        "note": note,
        "payment": entities.get("payment") or "PAID",
        "date": entities.get("date"),
        "input_text": text
    }
