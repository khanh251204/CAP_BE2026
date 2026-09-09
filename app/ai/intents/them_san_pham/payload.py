from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của them_san_pham thành payload chuẩn.
    """
    return {
        "name": entities.get("product"),
        "default_unit": entities.get("unit"),
        "unit_price": entities.get("price")
    }
