from typing import Any


def validate(entities: dict[str, Any]) -> dict:
    """
    Chốt sổ (chot_so) không bắt buộc tham số: thiếu kỳ thì mặc định chốt hôm nay.
    """
    return {
        "success": True,
        "missing_fields": []
    }
