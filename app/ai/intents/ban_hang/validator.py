from typing import Any

REQUIRED_FIELDS = [
    "product",
    "quantity",
    "unit"
]


def validate(entities: dict[str, Any]) -> dict:
    """
    Validate dữ liệu đầu vào của intent ban_hang.
    """
    missing_fields = []
    for field in REQUIRED_FIELDS:
        val = entities.get(field)
        if val is None or val == "":
            missing_fields.append(field)

    if missing_fields:
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    return {
        "success": True,
        "missing_fields": []
    }
