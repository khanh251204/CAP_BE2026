"""
Khôi phục dấu tiếng Việt cho văn bản OCR của hóa đơn in không dấu ("Tong cong", "Tien thua tra lai").

Luồng: phát hiện dòng tiếng Việt không dấu -> nhờ LLM (Groq, dùng chung pool key) thêm dấu -> KIỂM TRA TỪNG DÒNG.
Dòng nào bỏ dấu đi mà không khớp dòng gốc (LLM lỡ sửa số, mã, thêm bớt chữ) thì giữ bản gốc,
nên bước này không thể làm đổi số tiền hay mã số. LLM lỗi thì trả nguyên văn.
"""
import logging
import re
from typing import Dict

from app.ai.ocr.text_utils import strip_accents

logger = logging.getLogger(__name__)

RESTORE_MODEL = "openai/gpt-oss-120b"

_DIAC = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")

# Từ hay gặp trên hóa đơn (dạng không dấu) để nhận ra dòng là tiếng Việt, tránh đụng vào tên hàng nước ngoài
_VN_WORDS = set("""
tong cong thue tien mat so luong gia ngay hang hoa don thanh toan tra lai nguoi mua ten phuong thuc chi nhanh
cong ty thu ngan khach dua thua chuyen khoan phieu giao nhap ban cho tai pho nang truoc sau giam dich vu
khao sat chat cuu dung tieu ma the sdt dia chi ngay gio hom nay kho xuat ncc nha cung cap cua cam on quy
""".split())

SYSTEM_PROMPT = (
    "Bạn khôi phục dấu tiếng Việt cho văn bản OCR của hóa đơn / phiếu mua bán bị mất dấu.\n"
    "Quy tắc:\n"
    "1. Chỉ thêm dấu (thanh, mũ, ă â ê ô ơ ư, đ) dựa vào ngữ cảnh mua bán; chọn từ hợp nghĩa nhất.\n"
    "2. GIỮ NGUYÊN: chữ số, mã số, ký hiệu, dấu câu, từ tiếng Anh, tên thương hiệu, từ viết tắt "
    "(ví dụ MEGA MARKET, CROISSANT, WRF, 70G, GTGT).\n"
    "3. Giữ nguyên số dòng và thứ tự dòng; không thêm, bớt, đổi chữ; không gộp hay tách dòng.\n"
    "4. Dòng đã có dấu thì giữ nguyên.\n"
    "5. Chỉ trả về văn bản đã khôi phục dấu, không giải thích, không dùng markdown."
)


def _has_diacritics(line: str) -> bool:
    return any(c.lower() in _DIAC for c in line)


def line_needs_restore(line: str) -> bool:
    """Dòng không có chữ có dấu nào nhưng chứa từ tiếng Việt quen thuộc."""
    if _has_diacritics(line):
        return False
    return any(w in _VN_WORDS for w in re.findall(r"[a-z]+", line.lower()))


def needs_restore(text: str) -> bool:
    return any(line_needs_restore(l) for l in (text or "").splitlines())


def _norm(line: str) -> str:
    # Giữ hoa/thường: chỉ chấp nhận khác biệt về dấu
    return re.sub(r"\s+", " ", strip_accents(line)).strip()


def _clean_llm_output(s: str) -> str:
    s = re.sub(r"<think>.*?</think>", "", s or "", flags=re.DOTALL).strip()
    s = re.sub(r"^```\w*\n|\n```$", "", s)
    return s.strip("\n")


def verify_merge(original: str, restored: str) -> Dict:
    """Ghép kết quả LLM với bản gốc theo từng dòng; dòng không khớp giữ bản gốc."""
    orig_lines, new_lines = original.splitlines(), restored.splitlines()
    if len(orig_lines) != len(new_lines):
        return {"text": original, "changed": 0, "rejected": len(orig_lines), "reason": "lệch số dòng"}
    out, changed, rejected = [], 0, 0
    for o, n in zip(orig_lines, new_lines):
        if o == n or _norm(o) != _norm(n):
            if o != n:
                rejected += 1
            out.append(o)
        else:
            out.append(n)
            changed += 1
    return {"text": "\n".join(out), "changed": changed, "rejected": rejected, "reason": None}


def _call_groq(text: str) -> str:
    from app.ai.llm.groq_client_pool import get_groq_pool
    resp = get_groq_pool().call(lambda c: c.chat.completions.create(
        model=RESTORE_MODEL, temperature=0.0, reasoning_effort="low",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
    ))
    return resp.choices[0].message.content or ""


def restore_diacritics(text: str, enabled: bool = True) -> Dict:
    """Trả {"text", "applied", "changed", "rejected", "reason"}. Không cần khôi phục thì trả nguyên văn."""
    result = {"text": text, "applied": False, "changed": 0, "rejected": 0, "reason": None}
    if not enabled or not needs_restore(text):
        result["reason"] = "tắt" if not enabled else "không có dòng nào thiếu dấu"
        return result
    try:
        raw = _call_groq(text)
    except Exception as e:  # noqa: BLE001 - thêm dấu chỉ là bước phụ, lỗi thì giữ nguyên văn
        logger.warning("[OCR] Khôi phục dấu thất bại: %s", e)
        result["reason"] = "LLM không khả dụng"
        return result
    merged = verify_merge(text, _clean_llm_output(raw))
    result.update(text=merged["text"], applied=merged["changed"] > 0, changed=merged["changed"],
                  rejected=merged["rejected"], reason=merged["reason"])
    return result
