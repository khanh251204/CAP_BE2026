from datetime import date
from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}đ"
    except (TypeError, ValueError):
        return "0đ"


def period_text(period_type: str, start: str, end: str) -> str:
    """Nhãn kỳ dễ đọc: 'ngày 28/10/2026', 'tháng 10/2026', 'quý 4/2026', 'năm 2026'."""
    try:
        s = date.fromisoformat(str(start)[:10])
    except ValueError:
        return f"{start} → {end}"
    if period_type == "DAY":
        return f"ngày {s.strftime('%d/%m/%Y')}"
    if period_type == "MONTH":
        return f"tháng {s.month}/{s.year}"
    if period_type == "QUARTER":
        return f"quý {(s.month - 1) // 3 + 1}/{s.year}"
    if period_type == "YEAR":
        return f"năm {s.year}"
    return f"{start} → {end}"


class ChotSoHandler:
    """
    Business workflow cho intent: chot_so
    1. Suy ra kỳ chốt từ câu nói (mặc định hôm nay).
    2. Gọi MCP preview_closing xem trước số liệu (không ghi DB).
    3. Kỳ đã chốt -> báo lại; chưa chốt -> waiting_confirmation.
    4. Xác nhận -> MCP close_period (ClosingService.create_closing).
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "chot_so"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result.get("message")
            }

        payload = build_payload(entities=entities, text=text)
        if payload.get("error"):
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["date"],
                "message": payload["error"]
            }
        payload.pop("error", None)

        preview = normalize_mcp_result(await call_mcp_tool(
            "preview_closing",
            {
                "payload": payload,
                "user_id": user_id
            }
        ))
        if not isinstance(preview, dict) or not preview.get("success"):
            if isinstance(preview, dict):
                preview.setdefault("intent", intent)
            return preview

        p = preview.get("preview") or {}
        label = period_text(p.get("period_type"), p.get("period_start"), p.get("period_end"))

        if p.get("is_closed"):
            return {
                "success": False,
                "status": "already_closed",
                "intent": intent,
                "closing_id": p.get("existing_closing_id"),
                "preview": p,
                "message": f"Kỳ {label} đã được chốt sổ rồi. Muốn sửa số liệu, hãy mở lại kỳ này trong mục Chốt sổ."
            }

        summary = p.get("summary") or {}
        payload.update({
            "period_type": p.get("period_type"),
            "period_start": p.get("period_start"),
            "period_end": p.get("period_end"),
            "period_label": label,
            # Chỉ để hiển thị; khi xác nhận service tính lại số liệu mới nhất
            "summary": summary,
            "transaction_count": p.get("transaction_count", 0),
        })

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "close_period",
            "payload": payload,
            "message": (
                f"Chốt sổ {label}: {p.get('transaction_count', 0)} giao dịch, "
                f"doanh thu {_money(summary.get('total_sales'))}, "
                f"chi {_money(summary.get('total_expense'))}, "
                f"lợi nhuận {_money(summary.get('profit'))}. "
                f"Sau khi chốt sẽ không ghi lùi ngày vào kỳ này được nữa. Bạn có chắc muốn chốt sổ?"
            )
        }
