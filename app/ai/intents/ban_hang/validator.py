from typing import Any

# unit cũng bắt buộc (trừ dịch vụ) nhưng được kiểm tra trong handler (sau khi tra cứu sản phẩm)
# để gợi ý đúng đơn vị tính của sản phẩm / các đơn vị user đang dùng.
# price không bắt buộc: thiếu thì lấy giá bán trong danh mục.
REQUIRED_FIELDS = [
    "product",
    "quantity",
]

FIELD_LABELS = {
    "product": "tên sản phẩm",
    "quantity": "số lượng",
}


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
        labels = ", ".join(FIELD_LABELS[f] for f in missing_fields)
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": missing_fields,
            "message": f"Bạn chưa nói {labels}. Ví dụ: \"bán 2 lon Coca\"."
        }

    return {
        "success": True,
        "missing_fields": []
    }
