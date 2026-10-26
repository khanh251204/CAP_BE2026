from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product', 'quantity']


def validate(entities: dict[str, Any]) -> dict:
    """Nhập kho nội bộ (nhap_kho)."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='nhập kho 10 thùng bia',
    )
