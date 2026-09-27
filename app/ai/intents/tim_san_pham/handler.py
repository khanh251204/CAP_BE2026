from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class TimSanPhamHandler:
    """
    Business workflow cho intent: tim_san_pham (xem_san_pham)
    Xử lý:
    - Validate bắt buộc có trường 'product'.
    - Gọi MCP search_products.
    - Trả về danh sách sản phẩm tìm được.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "tim_san_pham"
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
            "search_products",
            {
                "name": payload["name"],
                "user_id": user_id
            }
        )
        return normalize_mcp_result(result)
