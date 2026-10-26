import asyncio
from typing import Any

from app.ai.intents.new_product_draft import new_product_note, prepare_new_product, user_units_hint
from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.supplier_model import Supplier
from app.repositories.inventory.inventory_lookup_repo import InventoryLookupRepository
from app.services.new_product_service import FLOW_PURCHASE, NEW_PRODUCT_KEY
from app.services.new_supplier_service import NEW_SUPPLIER_KEY, new_supplier_question
from app.services.sales_policy import (
    ERROR_INVALID_UNIT,
    order_total,
    is_unpaid_payment,
    is_unit_valid,
    invalid_unit_message,
)
from .validator import validate
from .payload import build_payload


def _lookup_supplier(user_id: int, supplier_name, supplier_id):
    """Tìm nhà cung cấp của user (không tự tạo mới). Trả về (id, name) hoặc (None, None)."""
    db = get_db_session()
    try:
        if supplier_id:
            row = db.query(Supplier).filter(Supplier.user_id == user_id, Supplier.supplier_id == supplier_id).first()
        else:
            row = InventoryLookupRepository(db).get_supplier_by_name(user_id, str(supplier_name))
        return (row.supplier_id, row.supplier_name) if row else (None, None)
    finally:
        db.close()


class MuaHangHandler:
    """
    Business workflow cho intent: mua_hang / nhap_hang (cùng một nghiệp vụ nhập hàng từ nhà cung cấp)
    1. Validate input entities
    2. Tra cứu sản phẩm qua MCP check_stock (khớp chính xác, tên mơ hồ thì hỏi lại)
       - Chưa có sản phẩm: chuẩn bị THÊM SẢN PHẨM MỚI (payload["new_product"]), tạo khi xác nhận
    3. Tra cứu Nhà cung cấp (chưa có thì hỏi tạo mới, tạo khi xác nhận)
    4. Xây dựng payload & tính tổng tiền / công nợ
    5. Trả về trạng thái chờ xác nhận (waiting_confirmation)
    """

    # Bắt buộc: product, quantity, giá nhập, đơn vị. Không lấy giá bán trong danh mục làm giá nhập.

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str | None = None,
        business_type: str | None = None
    ) -> dict:
        intent = intent or "mua_hang"

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

        # Số lượng nhập phải > 0
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
                "message": f"Số lượng nhập phải lớn hơn 0. Vui lòng nói rõ số lượng nhập."
            }

        product_name = entities.get("product")

        # 2. Tra cứu sản phẩm
        stock_result = normalize_mcp_result(await call_mcp_tool(
            "check_stock",
            {"payload": {"product_name": product_name}, "user_id": user_id}
        ))

        new_product_spec = None
        if stock_result.get("success"):
            product = stock_result
        elif stock_result.get("status") == "product_not_found":
            prepared = prepare_new_product(
                FLOW_PURCHASE, intent, user_id, product_name, entities,
                business_type or stock_result.get("business_type"),
            )
            if "response" in prepared:
                return prepared["response"]
            new_product_spec = prepared["spec"]
            product = {
                "product_id": None,
                "product_name": new_product_spec["product_name"],
                "default_unit": new_product_spec["default_unit"],
                "unit_price": None,
            }
        else:
            stock_result.setdefault("intent", intent)
            return stock_result

        # Đơn vị nhập phải khớp đơn vị tính của sản phẩm (chỉ với sản phẩm đã có trong DB)
        product_unit = product.get("default_unit")
        if not new_product_spec and not entities.get("unit"):
            hint = (
                f"Sản phẩm này đang tính theo '{product_unit}'."
                if product_unit
                else f"Sản phẩm này chưa có đơn vị tính, các đơn vị bạn đang dùng: {await asyncio.to_thread(user_units_hint, user_id)}."
            )
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["unit"],
                "product_name": product["product_name"],
                "message": (
                    f"Bạn chưa nói đơn vị tính khi nhập '{product['product_name']}'. "
                    f"{hint} "
                    f"Ví dụ: \"nhập {entities.get('quantity')} {product_unit or 'cái'} {product['product_name']} giá ...\"."
                ),
            }
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

        # 3. Payload cơ bản
        payload = build_payload(entities=entities, text=text)
        payload["product_name"] = product["product_name"]
        if product.get("product_id"):
            payload["product_id"] = product["product_id"]
        if new_product_spec:
            payload[NEW_PRODUCT_KEY] = new_product_spec
        if not payload.get("unit") and product.get("default_unit"):
            payload["unit"] = product["default_unit"]

        # 4. Nhà cung cấp: chưa có thì hỏi tạo mới, tạo thật khi người dùng xác nhận
        supplier_name = entities.get("supplier") or entities.get("supplier_name") or entities.get("vendor")
        supplier_id = entities.get("supplier_id")
        is_new_supplier = False
        if supplier_id or supplier_name:
            found_id, found_name = await asyncio.to_thread(_lookup_supplier, user_id, supplier_name, supplier_id)
            if not found_id and supplier_name:
                supplier_id = None
                is_new_supplier = True
            else:
                supplier_id, supplier_name = found_id or supplier_id, found_name or supplier_name
        if supplier_id:
            payload["supplier_id"] = supplier_id
        if supplier_name:
            payload["supplier_name"] = supplier_name
        if is_new_supplier:
            payload[NEW_SUPPLIER_KEY] = True

        # 5. Giá, số lượng, tổng tiền, thanh toán / công nợ
        unit_price = payload.get("unit_price")

        # Giá nhập phải > 0 (giá 0đ hoặc âm -> không cho nhập)
        if unit_price is not None:
            try:
                price_ok = float(unit_price) > 0
            except (ValueError, TypeError):
                price_ok = False
            if not price_ok:
                return {
                    "success": False,
                    "status": "invalid_price",
                    "intent": intent,
                    "missing_fields": ["price"],
                    "message": "Giá nhập phải lớn hơn 0đ. Vui lòng nói rõ giá nhập."
                }

        try:
            qty = float(payload.get("quantity", 1))
        except (ValueError, TypeError):
            qty = 1.0

        total_amount = order_total(entities.get("total_price"), unit_price, qty)
        if total_amount is not None:
            payload["total_amount"] = total_amount

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
        if has_debt and not supplier_id and not is_new_supplier:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["supplier"],
                "message": f"Đơn nhập hàng chưa thanh toán đủ / ghi nợ cần có thông tin Nhà cung cấp để ghi nợ."
            }

        price_text = f"{float(unit_price):,.0f}đ/{payload.get('unit') or ''}" if unit_price is not None else ""

        debt_info = ""
        if has_debt:
            supplier_label = f" cho NCC '{supplier_name}'" if supplier_name else ""
            if unpaid_val is not None and unpaid_val > 0:
                debt_info = f" (Chưa trả tiền - ghi nợ{supplier_label}: {unpaid_val:,.0f}đ)"
            else:
                debt_info = f" (Chưa trả tiền - ghi nợ{supplier_label})"

        supplier_info = f" từ nhà cung cấp '{supplier_name}'" if supplier_name else ""
        new_note = new_product_note(new_product_spec) if new_product_spec else ""

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "import_inventory",
            "new_product": new_product_spec,
            "payload": payload,
            "new_supplier": is_new_supplier,
            "message": (
                f"{new_supplier_question(supplier_name) if is_new_supplier else ''}"
                f"{'Nếu đồng ý, hệ thống sẽ tạo nhà cung cấp và ' if is_new_supplier else 'Bạn có chắc muốn '}"
                f"nhập "
                f"{payload['quantity']} "
                f"{payload.get('unit') or ''} '{product['product_name']}'"
                f"{supplier_info}"
                f"{' với giá ' + price_text if price_text else ''}"
                f"{debt_info}{new_note}{'.' if is_new_supplier else ' không?'}"
            )
        }
