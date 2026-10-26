from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product', 'quantity']


def validate(entities: dict[str, Any]) -> dict:
    """Xuất kho nội bộ (xuat_kho)."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='xuất kho 5 lon Coca',
    )
