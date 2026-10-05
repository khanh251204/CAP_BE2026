from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của tra_no_nha_cung_cap thành payload chuẩn.
    """
    return {
        "supplier_name": entities.get("supplier"),
        "supplier_id": entities.get("supplier_id"),
        "account_id": entities.get("account_id"),
        "amount": entities.get("amount") or entities.get("price"),
        "debt_id": entities.get("debt_id"),
        "date": entities.get("date"),
        "input_text": text
    }
