from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của tim_san_pham thành payload chuẩn.
    """
    return {
        "name": entities.get("product")
    }
