from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.customer_model import Customer
from .validator import validate
from .payload import build_payload


class KhachGhiNoHandler:
    """
    Business workflow cho intent: khach_ghi_no (hoặc ghi_no_khach_hang)
    Xử lý:
    - Nếu không nói giá: tự động tìm kiếm sản phẩm qua MCP search_products để lấy đơn giá.
    - Tìm Customer trong DB để lấy customer_id (không tự tạo mới).
    - Trả về waiting_confirmation để người dùng xác nhận.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "khach_ghi_no"
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

        customer_name = entities.get("customer") or entities.get("customer_name")
        if not customer_name:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["customer"],
                "message": "Thiếu thông tin khách hàng cần ghi nợ"
            }

        product_name = entities.get("product")
        raw_price = entities.get("price")
        raw_total_price = entities.get("total_price")
        raw_quantity = entities.get("quantity")
        unit = entities.get("unit")

        # Xác định quantity nếu có (mặc định 1.0)
        qty = 1.0
        if raw_quantity is not None:
            try:
                qty = float(raw_quantity)
                if qty <= 0:
                    qty = 1.0
            except (ValueError, TypeError):
                qty = 1.0

        unit_price = None
        original_amount = None

        # 1. Trường hợp người dùng KHÔNG nói giá -> search_products
        if raw_price is None and raw_total_price is None:
            if not product_name:
                return {
                    "success": False,
                    "status": "need_information",
                    "intent": intent,
                    "missing_fields": ["price"],
                    "message": "Thiếu thông tin giá hoặc sản phẩm để tính tiền ghi nợ"
                }

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
                    "status": "product_not_found",
                    "intent": intent,
                    "product_name": product_name,
                    "message": f"Không tìm thấy sản phẩm '{product_name}' trong danh sách để lấy giá."
                }

            product = products[0]
            product_unit_price = product.get("unit_price")
            if product_unit_price is None or str(product_unit_price).strip() == "":
                return {
                    "success": False,
                    "status": "price_not_found",
                    "intent": intent,
                    "product_name": product.get("product_name", product_name),
                    "message": f"Sản phẩm '{product.get('product_name', product_name)}' chưa có giá niêm yết. Vui lòng cung cấp giá."
                }

            try:
                unit_price = float(product_unit_price)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "status": "invalid_price",
                    "intent": intent,
                    "product_name": product.get("product_name", product_name),
                    "message": f"Giá của sản phẩm '{product.get('product_name', product_name)}' không hợp lệ."
                }

            original_amount = unit_price * qty
            product_name = product.get("product_name", product_name)
            if not unit:
                unit = product.get("default_unit")

        # 2. Trường hợp người dùng CÓ nói giá
        else:
            if raw_total_price is not None:
                try:
                    original_amount = float(raw_total_price)
                    unit_price = original_amount / qty if qty > 0 else original_amount
                except (ValueError, TypeError):
                    original_amount = float(raw_price or 0)
                    unit_price = original_amount
            else:
                try:
                    unit_price = float(raw_price)
                    if raw_quantity is not None:
                        original_amount = unit_price * qty
                    else:
                        original_amount = unit_price
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "status": "invalid_price",
                        "intent": intent,
                        "message": "Giá tiền ghi nợ không hợp lệ."
                    }

        # 3. Tìm Customer trong Database để lấy customer_id (không tự tạo mới)
        customer_id = entities.get("customer_id")
        if not customer_id:
            db = get_db_session()
            try:
                clean_customer_name = str(customer_name).strip()
                db_customer = (
                    db.query(Customer)
                    .filter(
                        Customer.user_id == user_id,
                        Customer.customer_name == clean_customer_name
                    )
                    .first()
                )
                if not db_customer:
                    db_customer = (
                        db.query(Customer)
                        .filter(
                            Customer.user_id == user_id,
                            Customer.customer_name.ilike(f"%{clean_customer_name}%")
                        )
                        .first()
                    )

                if not db_customer:
                    return {
                        "success": False,
                        "status": "customer_not_found",
                        "intent": intent,
                        "customer_name": customer_name,
                        "message": f"Không tìm thấy khách hàng '{customer_name}' trong hệ thống. Vui lòng tạo khách hàng trước."
                    }
                customer_id = db_customer.customer_id
                if hasattr(db_customer, "customer_name") and isinstance(db_customer.customer_name, str):
                    customer_name = db_customer.customer_name
            finally:
                db.close()

        payload = build_payload(entities=entities, text=text)
        payload["customer_id"] = customer_id
        payload["customer_name"] = customer_name
        payload["original_amount"] = original_amount
        payload["amount"] = original_amount
        if product_name:
            payload["product_name"] = product_name
        if unit_price is not None:
            payload["unit_price"] = unit_price
        payload["quantity"] = qty
        if unit:
            payload["unit"] = unit

        qty_str = f"{int(qty) if qty.is_integer() else qty}"
        detail_str = ""
        if product_name and unit_price is not None:
            unit_str = f" {unit}" if unit else ""
            detail_str = f" ({qty_str}{unit_str} {product_name} x {unit_price:,.0f}đ)"

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "ghi_no_khach_hang",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn ghi nợ cho khách hàng {customer_name} "
                f"số tiền {original_amount:,.0f}đ{detail_str} không?"
            )
        }
