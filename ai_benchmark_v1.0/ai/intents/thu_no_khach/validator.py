from typing import Any

REQUIRED_FIELDS = [
    "customer",
    "price"
]


def validate(entities: dict[str, Any], intent: str = "thu_no_khach") -> dict:
    """
    Validate dữ liệu đầu vào cho thu nợ khách hàng (thu_no_khach / thu_no_khach_hang).
    """
    fields_to_check = list(REQUIRED_FIELDS)
    if intent == "thu_no_khach" and "payment" in entities:
        pass  # payment có thể optional hoặc được fallback sang Tiền mặt

    missing_fields = []
    for field in fields_to_check:
        val = entities.get(field)
        if field == "price" and (entities.get("amount") or entities.get("total_price")):
            continue
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
