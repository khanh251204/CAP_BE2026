from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product', 'price']
EXAMPLE = 'thêm sản phẩm Pepsi giá 12k một lon'


def validate(entities: dict[str, Any]) -> dict:
    """Thêm sản phẩm (them_san_pham)."""
    result = check_required(
        entities,
        REQUIRED_FIELDS,
        example=EXAMPLE,
        labels={"price": "giá bán"},
    )
    if not result["success"]:
        return result

    # Giá âm (đã được gắn lại dấu từ câu nói) hoặc 0đ: chặn ngay ở bản nháp,
    # không để tới bước xác nhận mới báo lỗi kỹ thuật từ ProductService.
    try:
        positive = float(entities.get("price")) > 0
    except (TypeError, ValueError):
        positive = False
    if not positive:
        return {
            "success": False,
            "status": "need_information",
            "missing_fields": ["price"],
            "message": f'Giá bán phải lớn hơn 0đ. Vui lòng nói lại giá bán. Ví dụ: "{EXAMPLE}".',
        }

    return result
