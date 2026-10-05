from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.supplier_model import Supplier
from app.models.user_model import User
from .validator import validate
from .payload import build_payload


class NhapHangHandler:
    """
    Business workflow cho intent: nhap_hang
    Điều phối:
    1. Validate input entities
    2. Tìm kiếm sản phẩm qua MCP
    3. Tra cứu / kiểm tra Nhà cung cấp
    4. Xây dựng payload & tính toán công nợ / tổng tiền
    5. Trả về trạng thái chờ xác nhận (waiting_confirmation)
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "nhap_hang",
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

        # 2. Tìm kiếm sản phẩm qua MCP
        search_res = await call_mcp_tool(
            "search_products",
            {
                "name": product_name,
                "user_id": user_id
            }
        )
        result = normalize_mcp_result(search_res)
        if not result.get("success"):
            return result

        products = result.get("products", [])
        product = products[0] if products else None

        if not product:
            # Kiểm tra mô hình kinh doanh của User (ưu tiên trực tiếp từ JWT business_type)
            is_producer = False
            if business_type:
                is_producer = (str(business_type).strip().upper() == "PRODUCER")
            else:
                db = get_db_session()
                try:
                    user_obj = db.query(User).filter(User.user_id == user_id).first()
                    raw_bt = getattr(user_obj, "business_type", "") or ""
                    is_producer = (str(raw_bt).strip().upper() == "PRODUCER")
                finally:
                    db.close()

            if is_producer:
                # PRODUCER được phép mua/nhập nguyên liệu mới tự động
                product = {
                    "product_id": None,
                    "product_name": product_name,
                    "default_unit": entities.get("unit") or "",
                    "unit_price": entities.get("price") or entities.get("unit_price") or 0.0,
                    "is_new_raw_material": True
                }
            else:
                return {
                    "success": False,
                    "status": "product_not_found",
                    "intent": intent,
                    "product_name": product_name,
                    "message": f"Không tìm thấy sản phẩm '{product_name}' trong danh sách. Vui lòng tạo sản phẩm trước khi nhập hàng."
                }

        # 3. Build payload cơ bản
        payload = build_payload(entities=entities, text=text)
        if product.get("product_id"):
            payload["product_id"] = product["product_id"]
        else:
            payload["product_name"] = product["product_name"]

        if not payload.get("unit") and product.get("default_unit"):
            payload["unit"] = product["default_unit"]

        # 4. Trích xuất / tìm kiếm Nhà cung cấp - Không tự tạo mới
        supplier_name = (
            entities.get("supplier")
            or entities.get("supplier_name")
            or entities.get("vendor")
        )
        supplier_id = entities.get("supplier_id")

        if not supplier_id and supplier_name:
            db = get_db_session()
            try:
                clean_supplier_name = str(supplier_name).strip()
                # 1. Exact match
                db_supplier = (
                    db.query(Supplier)
                    .filter(
                        Supplier.user_id == user_id,
                        Supplier.supplier_name == clean_supplier_name
                    )
                    .first()
                )
                # 2. Fuzzy match
                if not db_supplier:
                    db_supplier = (
                        db.query(Supplier)
                        .filter(
                            Supplier.user_id == user_id,
                            Supplier.supplier_name.ilike(f"%{clean_supplier_name}%")
                        )
                        .first()
                    )

                if db_supplier:
                    supplier_id = db_supplier.supplier_id
                    supplier_name = db_supplier.supplier_name
                else:
                    return {
                        "success": False,
                        "status": "supplier_not_found",
                        "intent": intent,
                        "supplier_name": supplier_name,
                        "message": f"Không tìm thấy nhà cung cấp '{supplier_name}' trong hệ thống. Vui lòng tạo nhà cung cấp trước."
                    }
            finally:
                db.close()
        elif supplier_id and not supplier_name:
            db = get_db_session()
            try:
                db_supplier = (
                    db.query(Supplier)
                    .filter(
                        Supplier.user_id == user_id,
                        Supplier.supplier_id == supplier_id
                    )
                    .first()
                )
                if db_supplier:
                    supplier_name = db_supplier.supplier_name
            finally:
                db.close()

        if supplier_id:
            payload["supplier_id"] = supplier_id
        if supplier_name:
            payload["supplier_name"] = supplier_name

        # 5. Xử lý giá, số lượng, tổng tiền và thanh toán / công nợ
        unit_price = payload.get("unit_price")
        try:
            qty = float(payload.get("quantity", 1))
        except (ValueError, TypeError):
            qty = 1.0

        total_amount = None
        if unit_price is not None:
            try:
                total_amount = float(unit_price) * qty
            except (ValueError, TypeError):
                total_amount = None

        raw_payment = str(entities.get("payment") or "").strip().upper()
        unpaid_keywords = [
            "CHƯA TRẢ", "CHƯA THANH TOÁN", "CHUA TRA", "CHUA THANH TOAN",
            "NỢ", "NO", "PENDING", "UNPAID"
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
        if has_debt and not supplier_id:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["supplier"],
                "message": "Đơn hàng nhập chưa thanh toán đủ / ghi nợ cần có thông tin Nhà cung cấp để ghi nợ."
            }

        price_text = (
            f"{unit_price:,}đ/{payload['unit']}"
            if unit_price is not None
            else ""
        )

        debt_info = ""
        if has_debt:
            supplier_label = f" cho NCC '{supplier_name}'" if supplier_name else ""
            if unpaid_val is not None and unpaid_val > 0:
                debt_info = f" (Chưa trả tiền - ghi nợ{supplier_label}: {unpaid_val:,.0f}đ)"
            else:
                debt_info = f" (Chưa trả tiền - ghi nợ{supplier_label})"

        supplier_info = f" từ nhà cung cấp '{supplier_name}'" if supplier_name else ""

        raw_mat_label = " nguyên liệu mới" if product.get("is_new_raw_material") else ""

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "import_inventory",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn nhập "
                f"{payload['quantity']} "
                f"{payload.get('unit') or ''}"
                f"{raw_mat_label} '{product['product_name']}'"
                f"{supplier_info}"
                f"{' với giá ' + price_text if price_text else ''}"
                f"{debt_info} không?"
            )
        }
