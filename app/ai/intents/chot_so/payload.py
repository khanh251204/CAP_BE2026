import re
from datetime import date, timedelta
from typing import Any, Optional

from app.ai.intents.bao_cao.payload import _fold


def resolve_closing_period(text: str, date_entity: Optional[str] = None, today: Optional[date] = None) -> dict:
    """
    Suy ra kỳ chốt sổ từ câu nói (mặc định: hôm nay).
    Chốt sổ chỉ hỗ trợ DAY / MONTH / QUARTER / YEAR (không có tuần).
    Trả về {"period_params": ...} hoặc {"error": ...} nếu người dùng nói kỳ không hỗ trợ.
    """
    today = today or date.today()
    s = _fold(f"{date_entity or ''} {text or ''}")

    if re.search(r"\btuan\b", s):
        return {"error": "Chỉ chốt sổ được theo ngày, tháng, quý hoặc năm. Ví dụ: \"chốt sổ hôm nay\", \"chốt sổ tháng này\"."}

    if re.search(r"\bhom qua\b", s):
        return {"period_params": {"period_type": "DAY", "date_val": (today - timedelta(days=1)).isoformat()}}

    if re.search(r"\bthang\b", s):
        year, month = today.year, today.month
        m = re.search(r"\bthang\s+(\d{1,2})\b", s)
        if m and 1 <= int(m.group(1)) <= 12:
            month = int(m.group(1))
            # "chốt sổ tháng 12" nói vào tháng 1 -> tháng 12 năm trước
            if month > today.month:
                year -= 1
        elif re.search(r"\bthang (truoc|roi)\b", s):
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        return {"period_params": {"period_type": "MONTH", "year": year, "month": month}}

    if re.search(r"\bquy\b", s):
        year, quarter = today.year, (today.month - 1) // 3 + 1
        m = re.search(r"\bquy\s+(\d)\b", s)
        if m and 1 <= int(m.group(1)) <= 4:
            quarter = int(m.group(1))
            if quarter > (today.month - 1) // 3 + 1:
                year -= 1
        elif re.search(r"\bquy (truoc|roi)\b", s):
            quarter -= 1
            if quarter == 0:
                year, quarter = year - 1, 4
        return {"period_params": {"period_type": "QUARTER", "year": year, "quarter": quarter}}

    if re.search(r"\bnam (nay|truoc|ngoai|roi)\b|\bca nam\b", s):
        year = today.year - 1 if re.search(r"\bnam (truoc|ngoai|roi)\b", s) else today.year
        return {"period_params": {"period_type": "YEAR", "year": year}}

    return {"period_params": {"period_type": "DAY", "date_val": today.isoformat()}}


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của chot_so thành payload chuẩn.
    """
    resolved = resolve_closing_period(text, entities.get("date"))
    return {
        "period_params": resolved.get("period_params"),
        "error": resolved.get("error"),
        "input_text": text,
    }
