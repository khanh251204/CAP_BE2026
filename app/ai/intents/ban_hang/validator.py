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
        from app.services.sales_policy import is_unpaid_payment

        labels = ", ".join(FIELD_LABELS[f] for f in missing_fields)
        product = entities.get("product") or "Coca"
        unit = entities.get("unit") or "lon"
        if is_unpaid_payment(entities.get("payment")):
            # Bán nợ: số lượng quyết định số tiền khách nợ → nhắc rõ
            customer = entities.get("customer")
            to_customer = f" cho {customer}" if customer else ""
            message = (
                f"Bạn chưa nói {labels} khi bán nợ{to_customer}. "
                f"Vui lòng nói rõ để tính đúng số tiền khách nợ. Ví dụ: \"bán nợ 2 {unit} {product}{to_customer}\"."
            )
        else:
            message = f"Bạn chưa nói {labels}. Ví dụ: \"bán 2 {unit} {product}\"."
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": missing_fields,
            "message": message,
        }

    return {
        "success": True,
        "missing_fields": []
    }
