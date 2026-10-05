from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class NhapKhoHandler:
    """
    Business workflow cho intent: nhap_kho
    Nghiệp vụ: Nhập tồn kho (chỉ thao tác kho, không phải mua hàng từ nhà cung cấp).
    Điều phối:
    1. Validate input entities (product, quantity)
    2. Tìm kiếm sản phẩm qua MCP
    3. Xây dựng payload chuẩn
    4. Trả về trạng thái chờ xác nhận (waiting_confirmation)
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "nhap_kho"
    ) -> dict:
        # 1. Validate
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "error",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        product_name = entities.get("product")

        # 2. Tìm kiếm sản phẩm qua MCP
        search_res = await call_mcp_tool(
            "search_products",
            {
                "name": product_name,
                "user_id": user_id
            }
        )
        result = normalize_mcp_result(search_res)
        if not result.get("success"):
            return result

        products = result.get("products", [])
        if not products:
            return {
                "success": False,
                "status": "product_not_found",
                "intent": intent,
                "product_name": product_name,
                "message": f"Không tìm thấy sản phẩm '{product_name}' trong hệ thống. Vui lòng tạo sản phẩm trước khi nhập kho."
            }

        product = products[0]

        # 3. Build payload
        payload = build_payload(entities=entities, text=text)
        payload["product_id"] = product["product_id"]
        if not payload.get("unit") and product.get("default_unit"):
            payload["unit"] = product["default_unit"]

        unit_str = f" {payload['unit']}" if payload.get("unit") else ""

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "nhap_kho",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn nhập kho "
                f"{payload['quantity']}{unit_str} "
                f"{product['product_name']}?"
            )
        }
