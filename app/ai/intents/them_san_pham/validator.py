from typing import Any

from app.ai.intents.missing_info import check_required, is_not_positive

REQUIRED_FIELDS = ['product', 'price']


def validate(entities: dict[str, Any]) -> dict:
    """Thêm sản phẩm (them_san_pham). Giá bán phải là số lớn hơn 0."""
    result = check_required(
        entities,
        REQUIRED_FIELDS,
        example='thêm sản phẩm Pepsi giá 12k một lon',
        labels={"price": "giá bán"},
    )
    if result["success"] and is_not_positive(entities.get("price")):
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": ["price"],
            "message": 'Giá bán phải lớn hơn 0đ. Ví dụ: "thêm sản phẩm Pepsi giá 12k một lon".',
        }
    return result
