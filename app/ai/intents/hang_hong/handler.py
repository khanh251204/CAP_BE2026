from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.services.sales_policy import (
    ERROR_INSUFFICIENT_STOCK, ERROR_INVALID_UNIT, is_unit_valid, invalid_unit_message,
)
from .validator import validate
from .payload import build_payload


class HangHongHandler:
    """
    Business workflow cho intent: hang_hong
    1. Validate (product, quantity)
    2. Tra cứu sản phẩm & tồn kho qua MCP check_stock
    3. Không cho báo hỏng nhiều hơn tồn kho
    4. Trả về waiting_confirmation; ghi DAMAGE khi người dùng xác nhận (MCP report_damage)
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
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        stock_call = await call_mcp_tool(
            "check_stock",
            {
                "payload": {"product_name": entities.get("product")},
                "user_id": user_id
            }
        )
        product = normalize_mcp_result(stock_call)
        if not product.get("success"):
            product.setdefault("intent", intent)
            return product

        try:
            qty = float(entities.get("quantity"))
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["quantity"],
                "message": "Số lượng hàng hỏng phải lớn hơn 0."
            }

        product_unit = product.get("default_unit")
        if not is_unit_valid(entities.get("unit"), product_unit):
            return {
                "success": False,
                "status": "invalid_unit",
                "error_code": ERROR_INVALID_UNIT,
                "intent": intent,
                "product_name": product.get("product_name"),
                "unit_requested": entities.get("unit"),
                "default_unit": product_unit,
                "message": invalid_unit_message(product.get("product_name"), entities.get("unit"), product_unit),
            }

        in_stock = float(product.get("quantity") or 0)
        unit = product_unit or entities.get("unit") or ""
        if qty > in_stock:
            return {
                "success": False,
                "status": "out_of_stock",
                "error_code": ERROR_INSUFFICIENT_STOCK,
                "intent": intent,
                "product_name": product.get("product_name"),
                "quantity_requested": qty,
                "quantity_in_stock": in_stock,
                "message": f"'{product.get('product_name')}' chỉ còn {in_stock:g} {unit}, không thể báo hỏng {qty:g} {unit}."
            }

        payload = build_payload(entities=entities, text=text)
        payload["product_id"] = product["product_id"]
        payload["product_name"] = product.get("product_name")
        payload["unit"] = unit

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "report_damage",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn ghi nhận {qty:g} {unit} "
                f"{product.get('product_name')} bị hư hỏng (còn {in_stock:g} trong kho)?"
            )
        }
