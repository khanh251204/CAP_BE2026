from typing import Any

from app.ai.intents.new_product_draft import new_product_note, prepare_new_product
from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.services.sales_policy import ERROR_INVALID_UNIT, is_unit_valid, invalid_unit_message
from app.services.new_product_service import FLOW_STOCK_IN, NEW_PRODUCT_KEY
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
        intent: str = "nhap_kho",
        business_type: str | None = None
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

        # Số lượng nhập kho phải > 0
        try:
            qty_check = float(entities.get("quantity"))
        except (TypeError, ValueError):
            qty_check = 0.0
        if qty_check <= 0:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["quantity"],
                "message": "Số lượng nhập kho phải lớn hơn 0. Vui lòng nói rõ số lượng nhập."
            }

        product_name = entities.get("product")

        # 2. Tra cứu sản phẩm qua MCP check_stock (khớp chính xác trước, tên mơ hồ thì hỏi lại,
        #    bỏ qua sản phẩm đã ngừng kinh doanh) — cùng cách với xuat_kho / ban_hang
        stock_call = await call_mcp_tool(
            "check_stock",
            {
                "payload": {"product_name": product_name},
                "user_id": user_id
            }
        )
        product = normalize_mcp_result(stock_call)
        new_product_spec = None
        if not product.get("success"):
            if product.get("status") != "product_not_found":
                product.setdefault("intent", intent)
                return product
            # Chưa có sản phẩm: đề xuất thêm mới, tạo khi xác nhận
            prepared = prepare_new_product(
                FLOW_STOCK_IN, intent, user_id, product_name, entities,
                business_type or product.get("business_type"),
            )
            if "response" in prepared:
                return prepared["response"]
            new_product_spec = prepared["spec"]
            product = {"product_id": None, "product_name": new_product_spec["product_name"],
                       "default_unit": new_product_spec["default_unit"]}

        # Đơn vị nhập phải khớp đơn vị tính của sản phẩm (chỉ với sản phẩm đã có trong DB)
        product_unit = product.get("default_unit")
        if not new_product_spec and not is_unit_valid(entities.get("unit"), product_unit):
            return {
                "success": False,
                "status": "invalid_unit",
                "error_code": ERROR_INVALID_UNIT,
                "intent": intent,
                "product_name": product["product_name"],
                "unit_requested": entities.get("unit"),
                "default_unit": product_unit,
                "message": invalid_unit_message(product["product_name"], entities.get("unit"), product_unit),
            }
        if not new_product_spec and product_unit:
            # Dùng đúng cách viết đơn vị trong DB
            entities = {**entities, "unit": product_unit}

        # 3. Build payload
        payload = build_payload(entities=entities, text=text)
        payload["product_name"] = product["product_name"]
        if product.get("product_id"):
            payload["product_id"] = product["product_id"]
        if new_product_spec:
            payload[NEW_PRODUCT_KEY] = new_product_spec
        if not payload.get("unit") and product.get("default_unit"):
            payload["unit"] = product["default_unit"]

        unit_str = f" {payload['unit']}" if payload.get("unit") else ""

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "nhap_kho",
            "new_product": new_product_spec,
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn nhập kho "
                f"{payload['quantity']}{unit_str} "
                f"{product['product_name']}"
                f"{new_product_note(new_product_spec) if new_product_spec else ''}?"
            )
        }
