from typing import Any

REQUIRED_FIELDS = [
    "price"
]


def validate(entities: dict[str, Any]) -> dict:
    """
    Validate dữ liệu đầu vào cho chi_phi: bắt buộc có số tiền (price, amount hoặc total_price).
    """
    val = entities.get("price") or entities.get("amount") or entities.get("total_price")
    if val is None or val == "":
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": ["price"],
            "message": "Vui lòng cung cấp số tiền chi phí (VD: 'Chi 500k tiền điện')"
        }

    try:
        if float(val) <= 0:
            return {
                "success": False,
                "status": "error",
                "missing_fields": ["price"],
                "message": "Số tiền chi phí phải lớn hơn 0"
            }
    except (ValueError, TypeError):
        return {
            "success": False,
            "status": "error",
            "missing_fields": ["price"],
            "message": f"Số tiền chi phí '{val}' không hợp lệ"
        }

    return {
        "success": True,
        "missing_fields": []
    }
