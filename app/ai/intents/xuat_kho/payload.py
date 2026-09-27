from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của xuat_kho thành payload chuẩn.
    Không query DB, không gọi LLM hoặc MCP.
    """
    return {
        "product_name": entities.get("product"),
        "product_id": entities.get("product_id"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "date": entities.get("date"),
        "input_text": text
    }
