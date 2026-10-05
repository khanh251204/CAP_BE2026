from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của thu_no_khach thành payload chuẩn.
    """
    return {
        "customer_name": entities.get("customer"),
        "customer_id": entities.get("customer_id"),
        "account_id": entities.get("account_id"),
        "amount": entities.get("amount") or entities.get("price"),
        "debt_id": entities.get("debt_id"),
        "date": entities.get("date"),
        "input_text": text
    }
