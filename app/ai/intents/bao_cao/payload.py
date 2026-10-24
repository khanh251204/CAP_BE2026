import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Optional


def _fold(text: str) -> str:
    """Chữ thường + bỏ dấu tiếng Việt để so khớp từ khóa ổn định."""
    text = unicodedata.normalize("NFD", (text or "").lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def resolve_period_params(text: str, date_entity: Optional[str] = None, today: Optional[date] = None) -> dict:
    """
    Suy ra kỳ báo cáo từ câu nói (mặc định: hôm nay).
    Trả về tham số cho PeriodService.resolve_period.
    """
    today = today or date.today()
    s = _fold(f"{date_entity or ''} {text or ''}")

    if re.search(r"\bhom qua\b", s):
        return {"period_type": "DAY", "date_val": (today - timedelta(days=1)).isoformat()}
    if re.search(r"\btuan\b", s):
        return {"period_type": "WEEK", "date_val": today.isoformat()}
    if re.search(r"\bthang\b", s):
        return {"period_type": "MONTH", "year": today.year, "month": today.month}
    if re.search(r"\bquy\b", s):
        return {"period_type": "QUARTER", "year": today.year, "quarter": (today.month - 1) // 3 + 1}
    if re.search(r"\bnam nay\b", s):
        return {"period_type": "YEAR", "year": today.year}
    return {"period_type": "DAY", "date_val": today.isoformat()}


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của bao_cao thành payload chuẩn.
    """
    return {
        "date": entities.get("date"),
        "period_params": resolve_period_params(text, entities.get("date")),
        "input_text": text
    }
