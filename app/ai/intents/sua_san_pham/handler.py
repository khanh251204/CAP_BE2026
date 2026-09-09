from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate


class SuaSanPhamHandler:
    """
    Business workflow cho intent: sua_san_pham
    Xử lý:
    - Tìm sản phẩm cần sửa qua MCP search_products.
    - Tập hợp các thuộc tính cần thay đổi (tên mới, giá mới, đơn vị mới).
    - Trả về waiting_confirmation để người dùng xác nhận cập nhật.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "sua_san_pham"
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

        update_data = {}
        new_product_name = entities.get("new_product_name")
        if new_product_name:
            update_data["product_name"] = new_product_name

        if entities.get("price") is not None:
            update_data["unit_price"] = entities["price"]

        if entities.get("unit") is not None:
            update_data["default_unit"] = entities["unit"]

        if not update_data:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "message": "Bạn muốn sửa thông tin nào của sản phẩm?"
            }

        changes = []
        if "product_name" in update_data:
            changes.append(f"tên thành '{update_data['product_name']}'")
        if "unit_price" in update_data:
            changes.append(f"giá thành {update_data['unit_price']:,}đ")
        if "default_unit" in update_data:
            changes.append(f"đơn vị thành '{update_data['default_unit']}'")

        change_text = ", ".join(changes)

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "update_product",
            "payload": {
                "product_id": product_id,
                "product_name": product["product_name"],
                "data": update_data
            },
            "message": (
                f"Bạn có muốn sửa sản phẩm '{product['product_name']}' {change_text} không?"
            )
        }
