from typing import Any

# Dùng chung cho mua_hang / nhap_hang (cùng một nghiệp vụ).
# unit cũng bắt buộc nhưng được kiểm tra trong handler (sau khi tra cứu sản phẩm)
# để gợi ý đúng đơn vị tính của sản phẩm / các đơn vị user đang dùng.
REQUIRED_FIELDS = [
    "product",
    "quantity",
    "price",
]

FIELD_LABELS = {
    "product": "tên sản phẩm",
    "quantity": "số lượng",
    "price": "giá nhập",
}


def validate(entities: dict[str, Any]) -> dict:
    """Validate dữ liệu đầu vào của intent mua_hang / nhap_hang."""
    missing_fields = []
    for field in REQUIRED_FIELDS:
        val = entities.get(field)
        # Có tổng tiền (vd: "5 lốc 50k") thì đơn giá được tính từ tổng tiền / số lượng
        if field == "price" and val in (None, ""):
            val = entities.get("total_price")
        if val is None or val == "":
            missing_fields.append(field)

    if missing_fields:
        labels = ", ".join(FIELD_LABELS[f] for f in missing_fields)
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": missing_fields,
            "message": f"Bạn chưa nói {labels}. Ví dụ: \"nhập 10 lon Coca giá 8 nghìn\"."
        }

    return {
        "success": True,
        "missing_fields": []
    }
