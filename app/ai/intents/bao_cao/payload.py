from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của bao_cao thành payload chuẩn.
    """
    return {
        "date": entities.get("date"),
        "input_text": text
    }
