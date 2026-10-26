from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product', 'quantity']


def validate(entities: dict[str, Any]) -> dict:
    """Báo hàng hỏng (hang_hong). Đơn vị lấy mặc định từ sản phẩm nếu thiếu."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='hỏng 3 lon Coca',
    )
