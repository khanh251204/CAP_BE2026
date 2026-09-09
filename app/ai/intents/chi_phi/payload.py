from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của chi_phi thành payload chuẩn.
    """
    return {
        "amount": entities.get("price"),
        "date": entities.get("date"),
        "input_text": text
    }
