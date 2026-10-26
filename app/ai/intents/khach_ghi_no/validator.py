from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['customer']


def validate(entities: dict[str, Any]) -> dict:
    """Ghi nợ khách hàng (khach_ghi_no). Số tiền kiểm tra trong handler."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='ghi nợ chị Lan 200k',
    )
