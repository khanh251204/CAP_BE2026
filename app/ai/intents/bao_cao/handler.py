from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}đ"
    except (TypeError, ValueError):
        return "0đ"


class BaoCaoHandler:
    """
    Business workflow cho intent: bao_cao (READ-ONLY, không cần xác nhận)
    - Suy ra kỳ báo cáo từ câu nói (hôm nay / hôm qua / tuần / tháng / quý / năm nay).
    - Gọi MCP get_summary_report.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "bao_cao"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result.get("message") or "Bạn muốn xem báo cáo nào? Ví dụ: \"báo cáo doanh thu hôm nay\"."
            }

        payload = build_payload(entities=entities, text=text)
        result = normalize_mcp_result(await call_mcp_tool(
            "get_summary_report",
            {
                "payload": payload,
                "user_id": user_id
            }
        ))
        if not isinstance(result, dict) or not result.get("success"):
            return result

        report = result.get("report") or {}
        result["intent"] = intent
        result["message"] = (
            f"Doanh thu {_money(report.get('revenue', {}).get('total'))}, "
            f"nhập hàng {_money(report.get('purchase', {}).get('total'))}, "
            f"chi phí {_money(report.get('expense', {}).get('total'))}, "
            f"lợi nhuận {_money(report.get('profit', {}).get('total'))}."
        )
        return result
