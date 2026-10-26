from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['supplier']


def validate(entities: dict[str, Any]) -> dict:
    """Ghi nợ nhà cung cấp (ghi_no_nha_cung_cap). Số tiền nợ kiểm tra trong handler."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='ghi nợ nhà cung cấp Minh Phát 500k tiền hàng',
    )
