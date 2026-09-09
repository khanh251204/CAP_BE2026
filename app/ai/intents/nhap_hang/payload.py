from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của nhap_hang thành payload chuẩn.
    Không query DB, không gọi LLM hoặc MCP.
    """
    return {
        "product_name": entities.get("product"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "unit_price": entities.get("price"),
        "supplier_name": entities.get("supplier"),
        "payment_status": entities.get("payment"),
        "date": entities.get("date"),
        "input_text": text
    }
