from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class HangHongHandler:
    """
    Business workflow cho intent: hang_hong
    Xử lý:
    - Validate bắt buộc có trường 'price'.
    - Gọi MCP create_damaged_goods.
    - Trả về kết quả ghi nhận hàng hỏng.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "hang_hong"
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
            "create_damaged_goods",
            {
                "payload": payload,
                "user_id": user_id
            }
        )
        return normalize_mcp_result(result)
