"""
Chặn thẻ HTML / mã script trong dữ liệu người dùng nhập (đăng ký, đăng nhập, sản phẩm...).
App mobile dùng cùng quy tắc: VoiceCashBook/src/utils/inputSafety.ts.
"""
import re
from typing import Optional

_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>?|javascript\s*:|on\w+\s*=", re.IGNORECASE)


def contains_markup(value: Optional[str], strict: bool = True) -> bool:
    """strict: tên / địa chỉ không được có '<' hoặc '>'; strict=False (mật khẩu): chỉ chặn dạng thẻ / script."""
    if value is None:
        return False
    text = str(value)
    return bool((strict and ("<" in text or ">" in text)) or _TAG_RE.search(text))


def markup_message(label: str) -> str:
    return f"{label} không được chứa thẻ HTML hoặc mã script"


def reject_markup(value, label: str, strict: bool = True):
    """Raise ValueError (Pydantic / ORM validator) nếu có thẻ HTML / script; trả lại value."""
    if contains_markup(value, strict):
        raise ValueError(markup_message(label))
    return value
