from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['customer', 'price']


def validate(entities: dict[str, Any], intent: str = "thu_no_khach") -> dict:
    """Thu nợ khách hàng (thu_no_khach / thu_no_khach_hang). Đã nói amount/total_price thì không cần price."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='thu nợ chị Lan 300k',
        labels={"price": "số tiền thu"},
        alternatives={"price": ("amount", "total_price")},
    )
