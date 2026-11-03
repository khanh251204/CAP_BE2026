"""Xử lý văn bản OCR thuần Python (không phụ thuộc cv2 / torch)."""
import re
import unicodedata
from typing import List, Optional


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def collapse_repeats(text: str, max_run: int = 3) -> str:
    """Cắt đoạn lặp vô hạn của model (cùng một dòng lặp > max_run lần liên tiếp, bỏ qua số thứ tự đầu dòng)."""
    out, run, prev = [], 0, None
    for line in (text or "").splitlines():
        key = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
        run = run + 1 if key == prev else 1
        prev = key
        if run <= max_run:
            out.append(line)
    return "\n".join(out)


_NUM_RE = re.compile(r"\d[\d.,]*\d|\d")


def numbers(text: str) -> List[str]:
    """Mọi số trong văn bản, bỏ dấu phân cách nghìn: '1.250.000' -> '1250000'."""
    return [re.sub(r"\D", "", m) for m in _NUM_RE.findall(text or "")]


_NUM = r"(\d[\d.,]*)"
# Ưu tiên nhãn nói rõ "tổng phải trả"; cố ý không khớp "tổng điểm", "tổng số lượng"... để khỏi lấy nhầm.
_TOTAL_PATTERNS = [
    re.compile(r"tong\s*(?:so\s*)?(?:tien\s*)?(?:can\s*)?thanh\s*toan[^\d\n]{0,12}" + _NUM),
    re.compile(r"tong\s*cong[^\d\n]{0,12}" + _NUM),
    re.compile(r"tien\s*thanh\s*toan\b[^\n]*?" + _NUM + r"[ \t|]*$", re.M),
    re.compile(r"thanh\s*tien\s*tong[^\d\n]{0,12}" + _NUM),
    re.compile(r"\btong\s*tien\b[^\d\n]{0,12}" + _NUM),
]


def extract_total(text: str) -> Optional[int]:
    """Tổng tiền phải trả trên phiếu: lần xuất hiện cuối của nhãn ưu tiên cao nhất. Không có thì None."""
    s = strip_accents((text or "").lower())
    for pat in _TOTAL_PATTERNS:
        found = pat.findall(s)
        if found:
            digits = re.sub(r"\D", "", found[-1])
            if digits:
                return int(digits)
    return None
