from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của mua_hang thành payload chuẩn.
    Không query DB, không gọi LLM hoặc MCP.
    """
    return {
        "product_name": entities.get("product"),
        "product_id": entities.get("product_id"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "unit_price": entities.get("price"),
        "supplier_name": entities.get("supplier"),
        "supplier_id": entities.get("supplier_id"),
        "amount_paid": entities.get("amount_paid"),
        "payment_status": entities.get("payment"),
        "date": entities.get("date"),
        "input_text": text
    }
