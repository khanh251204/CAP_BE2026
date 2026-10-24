import asyncio
from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.repositories.inventory.inventory_lookup_repo import (
    InventoryLookupRepository,
    AmbiguousMatchError,
)
from app.services.sales_policy import (
    STRICT,
    MADE_TO_ORDER,
    NO_INVENTORY,
    RAW_MATERIAL_BLOCKED,
    ERROR_INSUFFICIENT_STOCK,
    ERROR_CANNOT_SELL_RAW_MATERIAL,
    get_sale_stock_policy,
    normalize_business_type,
    is_unpaid_payment,
)
from .validator import validate
from .payload import build_payload


def _lookup_customer(user_id: int, customer_name: str) -> tuple:
    """Tìm khách hàng của user (không tự tạo mới). Trả về (id, name) hoặc ném AmbiguousMatchError."""
    db = get_db_session()
    try:
        customer = InventoryLookupRepository(db).get_customer_by_name(user_id, str(customer_name))
        if customer:
            return customer.customer_id, customer.customer_name
        return None, None
    finally:
        db.close()


class BanHangHandler:
    """
    Business workflow cho intent: ban_hang
    Điều phối:
    1. Validate input entities
    2. Kiểm tra tồn kho qua MCP check_stock + áp dụng quy tắc business_type/product_type
    3. Tra cứu Khách hàng
    4. Xây dựng payload & tính toán đơn giá, công nợ / tổng tiền
    5. Trả về trạng thái chờ xác nhận (waiting_confirmation)

    Quy tắc tồn kho dùng chung với InventoryService.sell_goods (app/services/sales_policy.py)
    để bản nháp và bước xác nhận luôn cho cùng một kết quả.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "ban_hang",
        business_type: str | None = None
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

        # 2. Tra cứu sản phẩm & tồn kho
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

        # Dùng tên chuẩn trong DB thay vì tên LLM trích xuất
        product_name = stock_result.get("product_name") or product_name
        stock_quantity = stock_result.get("quantity", 0)

        try:
            qty_requested = float(quantity_requested)
            qty_in_stock = float(stock_quantity)
        except (TypeError, ValueError):
            qty_requested = 0
            qty_in_stock = 0

        if qty_requested <= 0:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["quantity"],
                "message": "Số lượng bán phải lớn hơn 0."
            }

        # business_type lấy từ bảng User (check_stock trả về); tham số truyền vào chỉ để ghi đè khi test
        business_type = normalize_business_type(business_type or stock_result.get("business_type"))
        policy = get_sale_stock_policy(business_type, stock_result.get("product_type"))

        if policy == RAW_MATERIAL_BLOCKED:
            return {
                "success": False,
                "status": ERROR_CANNOT_SELL_RAW_MATERIAL,
                "error_code": ERROR_CANNOT_SELL_RAW_MATERIAL,
                "intent": intent,
                "product_name": product_name,
                "message": f"Sản phẩm '{product_name}' là nguyên liệu sản xuất (RAW_MATERIAL), không thể bán trực tiếp dưới dạng thành phẩm."
            }

        unit_label = entities.get("unit") or stock_result.get("default_unit") or ""
        if policy == STRICT and qty_requested > qty_in_stock:
            return {
                "success": False,
                "status": "out_of_stock",
                "error_code": ERROR_INSUFFICIENT_STOCK,
                "intent": intent,
                "product_name": product_name,
                "quantity_requested": qty_requested,
                "quantity_in_stock": qty_in_stock,
                "message": (
                    f"Hàng không đủ! "
                    f"'{product_name}' còn {qty_in_stock:g} {unit_label}, "
                    f"bạn muốn bán {qty_requested:g} {unit_label}."
                )
            }

        # 3. Tìm Khách hàng (không tự tạo mới)
        customer_name = entities.get("customer") or entities.get("customer_name")
        customer_id = entities.get("customer_id")

        if not customer_id and customer_name:
            try:
                found_id, found_name = await asyncio.to_thread(_lookup_customer, user_id, customer_name)
            except AmbiguousMatchError as amb:
                return {
                    "success": False,
                    "status": "need_information",
                    "intent": intent,
                    "missing_fields": ["customer"],
                    "candidates": amb.candidates,
                    "message": str(amb)
                }
            if not found_id:
                return {
                    "success": False,
                    "status": "customer_not_found",
                    "intent": intent,
                    "customer_name": customer_name,
                    "message": f"Không tìm thấy khách hàng '{customer_name}' trong hệ thống. Vui lòng tạo khách hàng trước."
                }
            customer_id, customer_name = found_id, found_name

        payload = build_payload(entities=entities, text=text)
        payload["product_name"] = product_name
        if stock_result.get("product_id"):
            payload["product_id"] = stock_result["product_id"]
        if customer_id:
            payload["customer_id"] = customer_id
        if customer_name:
            payload["customer_name"] = customer_name

        # Đơn giá & đơn vị tính mặc định từ sản phẩm nếu chưa có
        if not payload.get("unit") and stock_result.get("default_unit"):
            payload["unit"] = stock_result["default_unit"]

        unit_price = payload.get("unit_price")
        if unit_price is None and stock_result.get("unit_price"):
            unit_price = stock_result["unit_price"]
            payload["unit_price"] = unit_price

        # 4. Tổng tiền và thanh toán / công nợ
        total_amount = None
        if unit_price is not None:
            try:
                total_amount = float(unit_price) * qty_requested
            except (ValueError, TypeError):
                total_amount = None

        is_unpaid = is_unpaid_payment(entities.get("payment"))

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

        has_debt = is_unpaid or (unpaid_val is not None and unpaid_val > 0)

        # Phát sinh nợ nhưng không có khách hàng -> cần khách hàng để ghi nợ
        if has_debt and not customer_id:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["customer"],
                "message": "Đơn hàng bán chưa thanh toán đủ / ghi nợ cần có thông tin Khách hàng để ghi nợ."
            }

        price_text = (
            f"{float(unit_price):,.0f}đ/{payload.get('unit') or ''}"
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

        stock_suffix = ""
        if policy == MADE_TO_ORDER and qty_in_stock < qty_requested:
            stock_suffix = " (chế biến/sản xuất theo yêu cầu)"
        elif policy != NO_INVENTORY:
            stock_suffix = f" (còn {qty_in_stock:g} trong kho)"

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
                f"{debt_info}"
                f"{stock_suffix}?"
            )
        }
