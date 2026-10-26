from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product', 'price']


def validate(entities: dict[str, Any]) -> dict:
    """Thêm sản phẩm (them_san_pham)."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='thêm sản phẩm Pepsi giá 12k một lon',
        labels={"price": "giá bán"},
    )
