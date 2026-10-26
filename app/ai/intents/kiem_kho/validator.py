from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['product']


def validate(entities: dict[str, Any]) -> dict:
    """Kiểm kho (kiem_kho)."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='kiểm kho Coca',
    )
