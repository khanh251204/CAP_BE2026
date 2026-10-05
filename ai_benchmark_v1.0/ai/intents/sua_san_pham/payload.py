from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của sua_san_pham thành payload chuẩn.
    """
    return {
        "product_name": entities.get("product"),
        "new_product_name": entities.get("new_product_name"),
        "product_id": entities.get("product_id"),
        "unit": entities.get("unit"),
        "unit_price": entities.get("price"),
        "input_text": text
    }
