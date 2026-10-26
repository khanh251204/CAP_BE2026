from typing import Any

from app.ai.intents.missing_info import check_required

REQUIRED_FIELDS = ['supplier']


def validate(entities: dict[str, Any]) -> dict:
    """Trả nợ nhà cung cấp (tra_no_nha_cung_cap). Số tiền kiểm tra trong handler (hỗ trợ 'trả hết')."""
    return check_required(
        entities,
        REQUIRED_FIELDS,
        example='trả nợ nhà cung cấp Minh Phát 500k',
    )
