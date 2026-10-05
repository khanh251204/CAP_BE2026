import re
import unicodedata
from typing import Optional


def remove_vietnamese_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để chuẩn hóa so sánh chuỗi."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return text.lower().strip()


def normalize_intent(intent: Optional[str]) -> str:
    """
    Chuẩn hóa intent để đồng bộ giữa nhãn ground-truth (có dấu) và mô hình (không dấu/aliases).
    """
    if not intent:
        return "unknown"
    normalized = remove_vietnamese_accents(intent).replace(" ", "_").replace("-", "_")

    # Intent alias mapping
    if normalized in ["ban_hang", "banhang"]:
        return "ban_hang"
    if normalized in ["nhap_hang", "nhaphang", "mua_hang", "muahang", "nhap_kho", "nhapkho"]:
        return "nhap_hang"
    if normalized in ["chi_phi", "chiphi", "chi_tieu", "chitieu"]:
        return "chi_phi"
    return normalized


def normalize_unit(unit: Optional[str]) -> str:
    """Chuẩn hóa các đơn vị đồng nghĩa tiếng Việt."""
    if not unit:
        return ""
    u = remove_vietnamese_accents(str(unit)).strip()
    if u in ["kg", "ki", "ky", "can", "ki lo", "kilo"]:
        return "kg"
    if u in ["lang"]:
        return "lang"
    if u in ["tan"]:
        return "tan"
    if u in ["lit", "l"]:
        return "lit"
    if u in ["cai", "chiec"]:
        return "cai"
    if u in ["hop"]:
        return "hop"
    if u in ["chai", "lo"]:
        return "chai"
    if u in ["goi", "bich", "bao"]:
        return "goi"
    if u in ["ly", "coc"]:
        return "ly"
    if u in ["dia", "dia thuc an"]:
        return "dia"
    if u in ["to", "bat"]:
        return "to"
    return u


def normalize_product_name(name: Optional[str]) -> str:
    """Chuẩn hóa tên sản phẩm để so sánh fuzzy / exact mềm."""
    if not name:
        return ""
    norm = remove_vietnamese_accents(str(name)).strip()
    norm = re.sub(r'[^\w\s]', ' ', norm)
    norm = re.sub(r'\s+', ' ', norm).strip()
    return norm
