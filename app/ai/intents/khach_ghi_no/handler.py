from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.customer_model import Customer
from app.repositories.inventory.inventory_lookup_repo import AmbiguousMatchError, InventoryLookupRepository
from app.services.new_customer_service import NEW_CUSTOMER_KEY, new_customer_question
from .validator import validate
from .payload import build_payload


class KhachGhiNoHandler:
    """
    Business workflow cho intent: khach_ghi_no (hoặc ghi_no_khach_hang)
    Xử lý:
    - Nếu không nói giá: tự động tìm kiếm sản phẩm qua MCP search_products để lấy đơn giá.
    - Tìm Customer trong DB để lấy customer_id; chưa có thì hỏi tạo mới (tạo khi xác nhận).
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
                "message": "Bạn chưa nói tên khách hàng cần ghi nợ. Ví dụ: \"ghi nợ chị Lan 200k\"."
            }

        product_name = entities.get("product")
        raw_price = entities.get("price")
        raw_total_price = entities.get("total_price")
        raw_quantity = entities.get("quantity")
        unit = entities.get("unit")

        # Bán nợ có hàng nhưng không nói số lượng (vd. "Ghi nợ chị Lan bia"):
        # không tự gán 1 — hỏi lại để tính đúng tiền nợ. Nói đủ số lượng thì agent đã chuyển sang ban_hang.
        # Chỉ ghi nợ một số tiền ("chị Lan nợ tiền bia 200k") thì không cần số lượng.
        has_quantity = raw_quantity not in (None, "")
        if product_name and not has_quantity and raw_price is None and raw_total_price is None:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["quantity"],
                "product_name": product_name,
                "message": (
                    f"Bạn chưa nói số lượng '{product_name}' bán nợ cho {customer_name}. "
                    f"Ví dụ: \"bán nợ 2 {unit or 'thùng'} {product_name} cho {customer_name}\"."
                ),
            }

        qty = 1.0
        if has_quantity:
            try:
                qty = float(raw_quantity)
            except (ValueError, TypeError):
                qty = 0.0
            if qty <= 0:
                return {
                    "success": False,
                    "status": "need_information",
                    "intent": intent,
                    "missing_fields": ["quantity"],
                    "message": "Số lượng bán nợ phải lớn hơn 0. Vui lòng nói lại số lượng.",
                }

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
                    "message": (
                        f"Bạn chưa nói số tiền ghi nợ cho {customer_name}. "
                        f"Ví dụ: \"ghi nợ {customer_name} 200k\"."
                    )
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

        # Số tiền ghi nợ phải > 0 (giá 0đ hoặc âm -> không cho ghi nợ)
        if original_amount is None or original_amount <= 0:
            if product_name and raw_price is None and raw_total_price is None:
                message = (
                    f"Sản phẩm '{product_name}' đang có giá 0đ nên không thể ghi nợ. "
                    f"Vui lòng nói rõ giá hoặc số tiền khách nợ."
                )
            else:
                message = "Số tiền ghi nợ phải lớn hơn 0. Vui lòng nói rõ số tiền khách nợ."
            return {
                "success": False,
                "status": "invalid_amount",
                "intent": intent,
                "missing_fields": ["price"],
                "message": message
            }

        # 3. Tìm Customer trong Database để lấy customer_id (không tự tạo mới)
        customer_id = entities.get("customer_id")
        is_new_customer = False
        if not customer_id:
            db = get_db_session()
            try:
                clean_customer_name = str(customer_name).strip()
                try:
                    db_customer = InventoryLookupRepository(db).get_customer_by_name(user_id, clean_customer_name)
                except AmbiguousMatchError as amb:
                    return {
                        "success": False,
                        "status": "need_information",
                        "intent": intent,
                        "missing_fields": ["customer"],
                        "candidates": amb.candidates,
                        "message": str(amb)
                    }

                if db_customer:
                    customer_id = db_customer.customer_id
                    if hasattr(db_customer, "customer_name") and isinstance(db_customer.customer_name, str):
                        customer_name = db_customer.customer_name
                else:
                    # Chưa có khách hàng: hỏi tạo mới, tạo thật khi người dùng xác nhận
                    is_new_customer = True
            finally:
                db.close()

        payload = build_payload(entities=entities, text=text)
        payload["customer_id"] = customer_id
        payload["customer_name"] = customer_name
        if is_new_customer:
            payload[NEW_CUSTOMER_KEY] = True
        payload["original_amount"] = original_amount
        payload["amount"] = original_amount
        payload["total_amount"] = original_amount
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
            "new_customer": is_new_customer,
            "message": (
                f"{new_customer_question(customer_name) if is_new_customer else ''}"
                f"{'Nếu đồng ý, hệ thống sẽ tạo khách hàng và ghi nợ cho ' if is_new_customer else 'Bạn có chắc muốn ghi nợ cho khách hàng '}"
                f"{customer_name} "
                f"số tiền {original_amount:,.0f}đ{detail_str}{'.' if is_new_customer else ' không?'}"
            )
        }
