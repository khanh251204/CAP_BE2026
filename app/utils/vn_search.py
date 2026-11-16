import re
import unicodedata
from sqlalchemy import func

_VN_CHAR_CLASSES = {
    "a": "[aàáảãạăằắẳẵặâầấẩẫậ]",
    "d": "[dđ]",
    "e": "[eèéẻẽẹêềếểễệ]",
    "i": "[iìíỉĩị]",
    "o": "[oòóỏõọôồốổỗộơờớởỡợ]",
    "u": "[uùúủũụưừứửữự]",
    "y": "[yỳýỷỹỵ]",
}


def strip_vn_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt và chuyển đ/Đ thành d/D."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def build_vn_regex_pattern(keyword: str) -> str:
    """
    Chuyển từ khóa tìm kiếm (có dấu hoặc không dấu) thành biểu thức REGEXP
    khớp không phân biệt hoa/thường và không phân biệt dấu tiếng Việt.
    """
    base = strip_vn_accents(keyword.strip()).lower()
    parts = []
    for ch in base:
        if ch in _VN_CHAR_CLASSES:
            parts.append(_VN_CHAR_CLASSES[ch])
        elif ch.isspace():
            parts.append(r"[[:space:]]+")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def vn_ilike(column, keyword: str):
    """
    Biểu thức SQLAlchemy tìm kiếm chuỗi con không phân biệt hoa/thường và
    không phân biệt dấu tiếng Việt (hỗ trợ cả collation utf8mb4_bin trên MySQL/TiDB).
    """
    pattern = build_vn_regex_pattern(keyword)
    if not pattern:
        return column.ilike("%%")
    return func.lower(column).op("REGEXP")(pattern)

