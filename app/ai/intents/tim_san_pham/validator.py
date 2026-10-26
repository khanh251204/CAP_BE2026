from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product']


def validate(entities: dict[str, Any]) -> dict:
    """Tìm sản phẩm (tim_san_pham)."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='tìm sản phẩm Coca',
    )
