from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload


class ThemSanPhamHandler:
    """
    Business workflow cho intent: them_san_pham
    Xử lý:
    - Validate bắt buộc có product, price.
    - Kiểm tra xem sản phẩm đã tồn tại trong hệ thống chưa qua MCP search_products.
    - Nếu đã tồn tại: cảnh báo product_already_exists.
    - Nếu chưa: trả về waiting_confirmation để người dùng xác nhận thêm.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "them_san_pham",
        business_type: str | None = None
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

        # Kiểm tra trùng TÊN CHÍNH XÁC (không phải tìm chứa chuỗi: có "Coca" vẫn thêm được "Coca Zero")
        dup_call = await call_mcp_tool(
            "find_duplicate_product",
            {
                "name": product_name,
                "user_id": user_id
            }
        )
        dup_result = normalize_mcp_result(dup_call)

        if not dup_result.get("success"):
            return dup_result

        if dup_result.get("exists"):
            existing = dup_result["product"]
            unit_price = existing.get("unit_price")
            try:
                price_text = f"{float(unit_price):,.0f}đ/{existing.get('default_unit', '')}"
            except (TypeError, ValueError):
                price_text = "chưa có giá"

            return {
                "success": False,
                "status": "product_already_exists",
                "intent": intent,
                "existing_product": existing,
                "message": (
                    f"Sản phẩm '{existing['product_name']}' đã tồn tại "
                    f"(giá: {price_text}). "
                    f"Bạn có muốn sửa thông tin sản phẩm này không?"
                )
            }

        payload = build_payload(entities=entities, text=text)
        if business_type:
            bt_upper = str(business_type).strip().upper()
            if bt_upper == "PRODUCER":
                payload["product_type"] = "FINISHED_GOOD"
            elif bt_upper == "RESELLER":
                payload["product_type"] = "RESALE"

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "create_product",
            "payload": payload,
            "message": (
                f"Bạn có muốn thêm sản phẩm "
                f"{payload['name']} "
                f"giá {payload['unit_price']:,}đ/"
                f"{payload['default_unit']} không?"
            )
        }
