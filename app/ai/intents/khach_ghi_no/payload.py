from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của khach_ghi_no thành payload chuẩn.
    """
    return {
        "customer_name": entities.get("customer"),
        "customer_id": entities.get("customer_id"),
        "product_name": entities.get("product"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "unit_price": entities.get("price"),
        "original_amount": entities.get("original_amount") or entities.get("price"),
        "amount": entities.get("original_amount") or entities.get("price"),
        "transaction_id": entities.get("transaction_id"),
        "date": entities.get("date"),
        "input_text": text
    }
