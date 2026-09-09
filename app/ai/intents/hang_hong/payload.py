from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của hang_hong thành payload chuẩn.
    """
    return {
        "product_name": entities.get("product"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "amount": entities.get("price"),
        "date": entities.get("date"),
        "input_text": text
    }
