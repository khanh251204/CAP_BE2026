from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class ChiPhiHandler:
    """
    Business workflow cho intent: chi_phi
    Xử lý:
    - Validate bắt buộc có trường 'price' (số tiền chi phí).
    - Gọi MCP create_expense.
    - Trả về kết quả ghi nhận chi phí.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "chi_phi"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": val_result.get("status", "need_information"),
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        payload = build_payload(entities=entities, text=text)
        cat_label = payload.get("category_name") or "Khác"
        amt = payload.get("amount", 0.0)

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "create_expense",
            "payload": payload,
            "message": f"Bạn có chắc muốn ghi nhận chi phí '{cat_label}' với số tiền {amt:,.0f}đ không?"
        }
