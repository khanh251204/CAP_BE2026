from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của kiem_kho thành payload chuẩn.
    """
    return {
        "product_name": entities.get("product")
    }
