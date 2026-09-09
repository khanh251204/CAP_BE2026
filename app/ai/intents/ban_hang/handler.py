from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.customer_model import Customer
from .validator import validate
from .payload import build_payload


class BanHangHandler:
    """
    Business workflow cho intent: ban_hang
    Điều phối:
    1. Validate input entities
    2. Kiểm tra tồn kho qua MCP check_stock
    3. Tra cứu / kiểm tra Khách hàng
    4. Xây dựng payload & tính toán đơn giá, công nợ / tổng tiền
    5. Trả về trạng thái chờ xác nhận (waiting_confirmation)
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "ban_hang"
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
            return stock_result

        stock_quantity = stock_result.get("quantity", 0)

        try:
            qty_requested = float(quantity_requested)
            qty_in_stock = float(stock_quantity)
        except (TypeError, ValueError):
            qty_requested = 0
            qty_in_stock = 0

        if qty_requested > qty_in_stock:
            return {
                "success": False,
                "status": "out_of_stock",
                "intent": intent,
                "product_name": product_name,
                "quantity_requested": qty_requested,
                "quantity_in_stock": qty_in_stock,
                "message": (
                    f"Hàng không đủ! "
                    f"'{product_name}' còn {qty_in_stock} {entities.get('unit', '')}, "
                    f"bạn muốn bán {qty_requested} {entities.get('unit', '')}."
                )
            }

        # 3. Trích xuất / tìm kiếm Khách hàng (customer) - Không tự tạo mới
        customer_name = entities.get("customer") or entities.get("customer_name")
        customer_id = entities.get("customer_id")

        if not customer_id and customer_name:
            db = get_db_session()
            try:
                clean_customer_name = str(customer_name).strip()
                # Exact match
                db_customer = (
                    db.query(Customer)
                    .filter(
                        Customer.user_id == user_id,
                        Customer.customer_name == clean_customer_name
                    )
                    .first()
                )
                # Fuzzy match
                if not db_customer:
                    db_customer = (
                        db.query(Customer)
                        .filter(
                            Customer.user_id == user_id,
                            Customer.customer_name.ilike(f"%{clean_customer_name}%")
                        )
                        .first()
                    )

                if db_customer:
                    customer_id = db_customer.customer_id
                    customer_name = db_customer.customer_name
                else:
                    return {
                        "success": False,
                        "status": "customer_not_found",
                        "intent": intent,
                        "customer_name": customer_name,
                        "message": f"Không tìm thấy khách hàng '{customer_name}' trong hệ thống. Vui lòng tạo khách hàng trước."
                    }
            finally:
                db.close()

        payload = build_payload(entities=entities, text=text)
        if stock_result.get("product_id"):
            payload["product_id"] = stock_result["product_id"]
        if customer_id:
            payload["customer_id"] = customer_id
        if customer_name:
            payload["customer_name"] = customer_name

        # Đơn giá & đơn vị tính mặc định từ tồn kho nếu chưa có
        if not payload.get("unit") and stock_result.get("default_unit"):
            payload["unit"] = stock_result["default_unit"]

        unit_price = payload.get("unit_price")
        if unit_price is None and stock_result.get("unit_price") is not None:
            unit_price = stock_result["unit_price"]
            payload["unit_price"] = unit_price

        # 4. Xử lý giá, số lượng, tổng tiền và thanh toán / công nợ
        try:
            qty = float(payload.get("quantity", qty_requested))
        except (ValueError, TypeError):
            qty = qty_requested

        total_amount = None
        if unit_price is not None:
            try:
                total_amount = float(unit_price) * qty
            except (ValueError, TypeError):
                total_amount = None

        raw_payment = str(entities.get("payment") or "").strip().upper()
        unpaid_keywords = [
            "CHƯA TRẢ", "CHƯA THANH TOÁN", "CHUA TRA", "CHUA THANH TOAN",
            "NỢ", "NO", "PENDING", "UNPAID", "GHI NỢ", "GHI NO"
        ]
        is_unpaid = any(kw in raw_payment for kw in unpaid_keywords)

        amount_paid = entities.get("amount_paid")
        if amount_paid is not None:
            try:
                amount_paid = float(amount_paid)
            except (ValueError, TypeError):
                amount_paid = 0.0
        elif is_unpaid:
            amount_paid = 0.0

        if amount_paid is not None:
            payload["amount_paid"] = amount_paid

        unpaid_val = None
        if total_amount is not None:
            if amount_paid is not None:
                unpaid_val = total_amount - amount_paid
            elif is_unpaid:
                unpaid_val = total_amount
        elif is_unpaid:
            unpaid_val = None

        has_debt = is_unpaid or (unpaid_val is not None and unpaid_val > 0)

        # Nếu phát sinh nợ nhưng không có thông tin khách hàng -> Báo lỗi cần khách hàng để ghi nợ
        if has_debt and not customer_id:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["customer"],
                "message": "Đơn hàng bán chưa thanh toán đủ / ghi nợ cần có thông tin Khách hàng để ghi nợ."
            }

        price_text = (
            f"{unit_price:,.0f}đ/{payload.get('unit') or ''}"
            if unit_price is not None
            else ""
        )

        debt_info = ""
        if has_debt:
            cust_label = f" cho khách '{customer_name}'" if customer_name else ""
            if unpaid_val is not None and unpaid_val > 0:
                debt_info = f" (Chưa thanh toán - ghi nợ{cust_label}: {unpaid_val:,.0f}đ)"
            else:
                debt_info = f" (Chưa thanh toán - ghi nợ{cust_label})"

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "export_inventory",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn bán "
                f"{payload['quantity']} "
                f"{payload.get('unit') or ''} "
                f"{payload['product_name']}"
                f"{' với giá ' + price_text if price_text else ''}"
                f"{debt_info} "
                f"(còn {qty_in_stock} trong kho)?"
            )
        }
