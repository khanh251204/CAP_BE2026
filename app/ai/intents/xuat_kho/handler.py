from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.services.sales_policy import (
    ERROR_INSUFFICIENT_STOCK, ERROR_INVALID_UNIT, is_unit_valid, invalid_unit_message, to_product_unit,
)
from .validator import validate
from .payload import build_payload


class XuatKhoHandler:
    """
    Business workflow cho intent: xuat_kho
    Nghiệp vụ: Xuất tồn kho (chỉ thao tác kho, không phải bán hàng cho khách).
    Điều phối:
    1. Validate input entities (product, quantity)
    2. Kiểm tra tồn kho qua MCP check_stock
    3. Xây dựng payload chuẩn
    4. Trả về trạng thái chờ xác nhận (waiting_confirmation)
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "xuat_kho"
    ) -> dict:
        # 1. Validate
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
        quantity_requested = entities.get("quantity", 0)

        # 2. Kiểm tra tồn kho trước khi xác nhận
        stock_call = await call_mcp_tool(
            "check_stock",
            {
                "payload": {"product_name": product_name},
                "user_id": user_id
            }
        )
        stock_result = normalize_mcp_result(stock_call)

        if not stock_result.get("success"):
            stock_result.setdefault("intent", intent)
            return stock_result

        # Dùng đúng tên / đơn vị sản phẩm trong DB
        product_name = stock_result.get("product_name") or product_name
        product_unit = stock_result.get("default_unit")
        # Quy đổi đơn vị cùng loại (kg <-> g, lít <-> ml...); khác loại mới báo lỗi
        converted = to_product_unit(entities, product_unit, stock_result.get("units"))
        if converted is None:
            return {
                "success": False,
                "status": "invalid_unit",
                "error_code": ERROR_INVALID_UNIT,
                "intent": intent,
                "product_name": product_name,
                "unit_requested": entities.get("unit"),
                "default_unit": product_unit,
                "message": invalid_unit_message(product_name, entities.get("unit"), product_unit),
            }
        entities = converted
        if product_unit:
            entities = {**entities, "unit": product_unit}

        stock_quantity = stock_result.get("quantity", 0)

        try:
            qty_requested = float(quantity_requested)
            qty_in_stock = float(stock_quantity)
        except (TypeError, ValueError):
            qty_requested = 0.0
            qty_in_stock = 0.0

        if qty_requested <= 0:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["quantity"],
                "message": "Số lượng xuất kho phải lớn hơn 0. Vui lòng nói rõ số lượng xuất."
            }

        if qty_requested > qty_in_stock:
            return {
                "success": False,
                "status": "out_of_stock",
                "error_code": ERROR_INSUFFICIENT_STOCK,
                "intent": intent,
                "product_name": product_name,
                "quantity_requested": qty_requested,
                "quantity_in_stock": qty_in_stock,
                "message": (
                    f"Hàng trong kho không đủ để xuất! "
                    f"'{product_name}' còn {qty_in_stock} {entities.get('unit', '')}, "
                    f"bạn muốn xuất {qty_requested} {entities.get('unit', '')}."
                )
            }

        # 3. Build payload
        payload = build_payload(entities=entities, text=text)
        payload["product_name"] = product_name
        if stock_result.get("product_id"):
            payload["product_id"] = stock_result["product_id"]
        if not payload.get("unit") and stock_result.get("default_unit"):
            payload["unit"] = stock_result["default_unit"]

        unit_str = f" {payload['unit']}" if payload.get("unit") else ""

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "xuat_kho",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn xuất kho "
                f"{payload['quantity']}{unit_str} "
                f"{payload['product_name']} "
                f"(còn {qty_in_stock} trong kho)?"
            )
        }
