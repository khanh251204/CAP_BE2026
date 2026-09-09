from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class BaoCaoHandler:
    """
    Business workflow cho intent: bao_cao
    Xử lý:
    - Gọi MCP get_transaction_report.
    - Trả về báo cáo giao dịch / doanh thu.
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
                "status": "error",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": "Thiếu thông tin bắt buộc"
            }

        payload = build_payload(entities=entities, text=text)
        result = await call_mcp_tool(
            "get_transaction_report",
            {
                "payload": payload,
                "user_id": user_id
            }
        )
        return normalize_mcp_result(result)
