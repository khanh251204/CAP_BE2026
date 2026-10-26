from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class KiemKhoHandler:
    """
    Business workflow cho intent: kiem_kho
    Xử lý:
    - Validate bắt buộc có trường 'product'.
    - Gọi MCP check_stock.
    - Trả về kết quả tồn kho.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "kiem_kho"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        payload = build_payload(entities=entities, text=text)
        result = await call_mcp_tool(
            "check_stock",
            {
                "payload": payload,
                "user_id": user_id
            }
        )
        return normalize_mcp_result(result)
