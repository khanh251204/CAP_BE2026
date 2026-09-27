from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của xoa_san_pham thành payload chuẩn.
    """
    return {
        "product_name": entities.get("product"),
        "product_id": entities.get("product_id")
    }
