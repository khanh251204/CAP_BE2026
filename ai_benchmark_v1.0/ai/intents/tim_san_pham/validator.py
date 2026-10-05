from typing import Any

REQUIRED_FIELDS = [
    "product"
]


def validate(entities: dict[str, Any]) -> dict:
    """
    Validate dữ liệu đầu vào cho tim_san_pham (xem_san_pham).
    """
    missing_fields = []
    for field in REQUIRED_FIELDS:
        val = entities.get(field)
        if val is None or val == "":
            missing_fields.append(field)

    if missing_fields:
        return {
            "success": False,
            "status": "error",
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    return {
        "success": True,
        "missing_fields": []
    }
