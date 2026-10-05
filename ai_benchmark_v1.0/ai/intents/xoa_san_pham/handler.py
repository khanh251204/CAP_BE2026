from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class XoaSanPhamHandler:
    """
    Business workflow cho intent: xoa_san_pham
    Xử lý:
    - Tìm sản phẩm cần xóa qua MCP search_products.
    - Trả về waiting_confirmation để người dùng xác nhận xóa.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "xoa_san_pham"
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

        product_name = entities.get("product")

        search_call = await call_mcp_tool(
            "search_products",
            {
                "name": product_name,
                "user_id": user_id
            }
        )
        search_result = normalize_mcp_result(search_call)

        if not search_result.get("success"):
            return search_result

        products = search_result.get("products", [])
        if not products:
            return {
                "success": False,
                "status": "not_found",
                "intent": intent,
                "message": f"Không tìm thấy sản phẩm '{product_name}'"
            }

        product = products[0]
        product_id = product["product_id"]

        payload = build_payload(entities=entities, text=text)
        payload["product_id"] = product_id
        payload["product_name"] = product["product_name"]

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "delete_product",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn xóa sản phẩm '{product['product_name']}' không?"
            )
        }
