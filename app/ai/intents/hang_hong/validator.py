from typing import Any

# Khớp với prompt intent.py: hang_hong cần product + quantity (unit lấy mặc định từ sản phẩm nếu thiếu)
REQUIRED_FIELDS = [
    "product",
    "quantity"
]


def validate(entities: dict[str, Any]) -> dict:
    """
    Validate dữ liệu đầu vào cho hang_hong.
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
