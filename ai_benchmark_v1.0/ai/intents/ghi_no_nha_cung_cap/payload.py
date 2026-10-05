from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của ghi_no_nha_cung_cap thành payload chuẩn.
    """
    return {
        "supplier_name": entities.get("supplier"),
        "supplier_id": entities.get("supplier_id"),
        "product_name": entities.get("product"),
        "quantity": entities.get("quantity"),
        "unit": entities.get("unit"),
        "unit_price": entities.get("price"),
        "original_amount": entities.get("original_amount") or entities.get("amount") or entities.get("price"),
        "amount": entities.get("original_amount") or entities.get("amount") or entities.get("price"),
        "transaction_id": entities.get("transaction_id"),
        "date": entities.get("date"),
        "input_text": text
    }
