from typing import Any


def validate(entities: dict[str, Any]) -> dict:
    """
    Validate dữ liệu đầu vào cho bao_cao.
    Báo cáo không bắt buộc tham số nào.
    """
    return {
        "success": True,
        "missing_fields": []
    }
