# app/ai/core/handlers.py
from typing import Any
from datetime import datetime
from decimal import Decimal

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.services.account_service import AccountService
from app.repositories.debt_repository import DebtRepository

# app/ai/agent/routes.py
# DEPRECATED: Vui lòng sử dụng app.ai.core.router.IntentRouter và các intent tương ứng

# ============================================================
# INTENT → MCP TOOL
# ============================================================

ROUTES = {

    # =========================
    # GIAO DỊCH
    # =========================

    "ban_hang": "export_inventory",
    "nhap_hang": "import_inventory",
    "mua_hang": "import_inventory",
    "nhap_kho": "nhap_kho",
    "xuat_kho": "xuat_kho",
    "kiem_kho": "check_stock",

    # =========================
    # PRODUCT
    # =========================

    "tim_san_pham": "search_products",
    "xem_san_pham": "search_products",

    # =========================
    # CÔNG NỢ KHÁCH
    # =========================

    "ghi_no_khach_hang": "ghi_no_khach_hang",
    "thu_no_khach_hang": "thu_no_khach_hang",
    "khach_ghi_no": "ghi_no_khach_hang",
    "thu_no_khach": "thu_no_khach_hang",

    # =========================
    # CÔNG NỢ NHÀ CUNG CẤP
    # =========================

    "ghi_no_nha_cung_cap": "ghi_no_nha_cung_cap",
    "ncc_ghi_no": "ghi_no_nha_cung_cap",
    "thu_no_nha_cung_cap": "thu_no_nha_cung_cap",
    "tra_no_nha_cung_cap": "thu_no_nha_cung_cap",
    "tra_no_ncc": "thu_no_nha_cung_cap",

    # =========================
    # CHI PHÍ / HÀNG HỎNG
    # =========================

    "chi_phi": "create_expense",
    "hang_hong": "create_damaged_goods",

    # =========================
    # BÁO CÁO
    # =========================

    "bao_cao": "get_transaction_report"
}


# ============================================================
# REQUIRED FIELDS
# ============================================================

REQUIRED_FIELDS = {

    "them_san_pham": [
        "product",
        "price"
    ],

    "sua_san_pham": [
        "product"
    ],

    "xoa_san_pham": [
        "product"
    ],

    "kiem_kho": [
        "product"
    ],

    "ban_hang": [
        "product",
        "quantity",
        "unit"
    ],

    "nhap_hang": [
        "product",
        "price",
        "quantity",
        "unit"
    ],

    "mua_hang": [
        "product",
        "price",
        "quantity",
        "unit"
    ],

    "nhap_kho": [
        "product",
        "quantity"
    ],

    "xuat_kho": [
        "product",
        "quantity"
    ],

    "ghi_no_khach_hang": [
        "customer"
    ],

    "thu_no_khach_hang": [
        "customer",
        "price"
    ],

    "khach_ghi_no": [
        "customer"
    ],

    "thu_no_khach": [
        "customer",
        "price",
        "payment"
    ],

    "ghi_no_nha_cung_cap": [
        "supplier"
    ],

    "ncc_ghi_no": [
        "supplier"
    ],

    "thu_no_nha_cung_cap": [
        "supplier"
    ],

    "tra_no_nha_cung_cap": [
        "supplier"
    ],

    "tra_no_ncc": [
        "supplier"
    ],

    "chi_phi": [
        "price"
    ],

    "hang_hong": [
        "price"
    ]
}


# app/ai/agent/payload_builder.py
# DEPRECATED: Vui lòng sử dụng payload.py trong từng intent tương ứng (app/ai/intents/<intent>/payload.py)

from typing import Any


def build_payload(
    intent: str,
    entities: dict[str, Any],
    text: str
) -> dict:

    if intent == "ban_hang":

        return {
            "product_name": entities.get("product"),
            "product_id": entities.get("product_id"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "customer_name": entities.get("customer"),
            "customer_id": entities.get("customer_id"),
            "amount_paid": entities.get("amount_paid"),
            "payment_status": entities.get("payment"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("nhap_hang", "mua_hang"):
        print("payment_status", entities.get("payment"))

        return {
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "supplier_name": entities.get("supplier"),
            "payment_status": entities.get("payment"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("nhap_kho", "xuat_kho"):
        return {
            "product_name": entities.get("product"),
            "product_id": entities.get("product_id"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "kiem_kho":

        return {
            "product_name": entities.get("product")
        }

    if intent in ("tim_san_pham", "xem_san_pham"):

        return {
            "name": entities.get("product")
        }

    if intent == "them_san_pham":

        return {
            "name": entities.get("product"),
            "default_unit": entities.get("unit"),
            "unit_price": entities.get("price")
        }

    if intent == "sua_san_pham":

        return {
            "product_name": entities.get("product"),
            "new_product_name": entities.get("new_product_name"),
            "product_id": entities.get("product_id"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "input_text": text
        }

    if intent == "xoa_san_pham":

        return {
            "product_name": entities.get("product"),
            "product_id": entities.get("product_id")
        }

    if intent in ("ghi_no_khach_hang", "khach_ghi_no"):

        return {
            "customer_name": entities.get("customer"),
            "customer_id": entities.get("customer_id"),
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "original_amount": entities.get("original_amount") or entities.get("price"),
            "amount": entities.get("original_amount") or entities.get("price"),
            "transaction_id": entities.get("transaction_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("thu_no_khach_hang", "thu_no_khach"):

        return {
            "customer_name": entities.get("customer"),
            "customer_id": entities.get("customer_id"),
            "account_id": entities.get("account_id"),
            "amount": entities.get("amount") or entities.get("price"),
            "debt_id": entities.get("debt_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("ghi_no_nha_cung_cap", "ncc_ghi_no"):

        return {
            "supplier_name": entities.get("supplier"),
            "supplier_id": entities.get("supplier_id"),
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "unit_price": entities.get("price"),
            "original_amount": entities.get("original_amount") or entities.get("amount") or entities.get("price"),
            "amount": entities.get("original_amount") or entities.get("amount") or entities.get("price"),
            "transaction_id": entities.get("transaction_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent in ("thu_no_nha_cung_cap", "tra_no_nha_cung_cap", "tra_no_ncc"):

        return {
            "supplier_name": entities.get("supplier"),
            "supplier_id": entities.get("supplier_id"),
            "account_id": entities.get("account_id"),
            "amount": entities.get("amount") or entities.get("price"),
            "debt_id": entities.get("debt_id"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "chi_phi":

        return {
            "amount": entities.get("price"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "hang_hong":

        return {
            "product_name": entities.get("product"),
            "quantity": entities.get("quantity"),
            "unit": entities.get("unit"),
            "amount": entities.get("price"),
            "date": entities.get("date"),
            "input_text": text
        }

    if intent == "bao_cao":

        return {
            "date": entities.get("date"),
            "input_text": text
        }

    return entities


# app/ai/core/handlers.py
# DEPRECATED: Vui lòng sử dụng các intent handlers tương ứng trong app/ai/intents/
# File này được duy trì để đảm bảo tương thích ngược với các test case cũ.

from typing import Any
from datetime import datetime
from decimal import Decimal

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.services.account_service import AccountService
from app.repositories.debt_repository import DebtRepository


# ============================================================
# VALIDATE HELPER
# ============================================================

def validate(intent: str, entities: dict[str, Any]) -> list[str]:

    required = REQUIRED_FIELDS.get(intent, [])
    missing = []

    for field in required:
        value = entities.get(field)
        if value is None or value == "":
            missing.append(field)

    return missing


# ============================================================
# SEARCH PRODUCT HELPER
# ============================================================

async def search_product(product_name: str, user_id: int) -> dict:

    result = await call_mcp_tool(
        "search_products",
        {
            "name": product_name,
            "user_id": user_id
        }
    )

    return normalize_mcp_result(result)


# ============================================================
# CHECK STOCK HELPER
# ============================================================

async def get_stock(product_name: str, user_id: int) -> dict:

    result = await call_mcp_tool(
        "check_stock",
        {
            "payload": {"product_name": product_name},
            "user_id": user_id
        }
    )

    return normalize_mcp_result(result)


# ============================================================
# BÁN HÀNG
# ============================================================

async def handle_sell(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:

    missing_fields = validate(intent=intent, entities=entities)

    if missing_fields:

        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    product_name = entities.get("product")
    quantity_requested = entities.get("quantity", 0)

    # --------------------------------------------------------
    # Kiểm tra tồn kho trước khi xác nhận
    # --------------------------------------------------------

    stock_result = await get_stock(
        product_name=product_name,
        user_id=user_id
    )

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

    # --------------------------------------------------------
    # Trích xuất / tìm kiếm Khách hàng (customer) - KHÔNG TỰ TẠO MỚI
    # --------------------------------------------------------
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

    payload = build_payload(intent=intent, entities=entities, text=text)
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

    # --------------------------------------------------------
    # Xử lý giá, số lượng, tổng tiền và thanh toán / công nợ
    # --------------------------------------------------------
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


# ============================================================
# NHẬP HÀNG
# ============================================================

async def handle_import(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:

    missing_fields = validate(intent=intent, entities=entities)

    if missing_fields:

        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    product_name = entities.get("product")

    result = await search_product(
        product_name=product_name,
        user_id=user_id
    )

    if not result.get("success"):
        return result

    products = result.get("products", [])

    if not products:

        return {
            "success": False,
            "status": "product_not_found",
            "intent": intent,
            "product_name": product_name,
            "message": (
                f"Không tìm thấy sản phẩm "
                f"'{product_name}' trong danh sách."
            )
        }

    product = products[0]

    payload = build_payload(intent=intent, entities=entities, text=text)
    payload["product_id"] = product["product_id"]

    # --------------------------------------------------------
    # Trích xuất / tìm kiếm Nhà cung cấp (supplier) - KHÔNG TỰ TẠO MỚI
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Xử lý giá, số lượng, tổng tiền và thanh toán / công nợ
    # --------------------------------------------------------
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
    unpaid_keywords = ["CHƯA TRẢ", "CHƯA THANH TOÁN", "CHUA TRA", "CHUA THANH TOAN", "NỢ", "NO", "PENDING", "UNPAID"]
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

    price_text = (
        f"{unit_price:,}đ/{payload['unit']}"
        if unit_price is not None
        else ""
    )

    debt_info = ""
    if is_unpaid or (amount_paid is not None and total_amount is not None and amount_paid < total_amount):
        supplier_label = f" cho NCC '{supplier_name}'" if supplier_name else ""
        if total_amount is not None:
            unpaid_val = total_amount - (amount_paid or 0.0)
            debt_info = f" (Chưa trả tiền - ghi nợ{supplier_label}: {unpaid_val:,.0f}đ)"
        else:
            debt_info = f" (Chưa trả tiền - ghi nợ{supplier_label})"

    supplier_info = f" từ nhà cung cấp '{supplier_name}'" if supplier_name else ""

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "import_inventory",
        "payload": payload,
        "message": (
            f"Bạn có chắc muốn nhập "
            f"{payload['quantity']} "
            f"{payload['unit']} "
            f"{product['product_name']}"
            f"{supplier_info}"
            f"{' với giá ' + price_text if price_text else ''}"
            f"{debt_info} không?"
        )
    }


# ============================================================
# GHI NỢ KHÁCH HÀNG
# ============================================================

async def handle_ghi_no_khach_hang(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    """
    Xử lý intent ghi nợ khách hàng:
    - Nếu người dùng KHÔNG nói giá: tự động dùng search_products để tìm đơn giá
      và tính tổng số tiền nợ = đơn giá * số lượng.
    - Tìm hoặc tự tạo Customer trong DB theo user_id để lấy customer_id.
    - Trả về waiting_confirmation để người dùng xác nhận trước khi lưu.
    """
    missing_fields = validate(intent=intent, entities=entities)

    if missing_fields:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
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

    # --------------------------------------------------------
    # 1. Trường hợp người dùng KHÔNG nói giá -> search_products
    # --------------------------------------------------------
    if raw_price is None and raw_total_price is None:
        if not product_name:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["price"],
                "message": "Thiếu thông tin giá hoặc sản phẩm để tính tiền ghi nợ"
            }

        # Dùng search_products để tìm giá sản phẩm
        search_result = await search_product(
            product_name=product_name,
            user_id=user_id
        )

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

    # --------------------------------------------------------
    # 2. Trường hợp người dùng CÓ nói giá
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # 3. Tìm Customer trong Database để lấy customer_id (KHÔNG TỰ TẠO MỚI)
    # --------------------------------------------------------
    customer_id = entities.get("customer_id")
    if not customer_id:
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

    payload = build_payload(intent=intent, entities=entities, text=text)
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


# ============================================================
# THU NỢ KHÁCH HÀNG
# ============================================================

async def handle_thu_no_khach_hang(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    """
    Xử lý intent thu nợ khách hàng:
    - Tìm khách hàng trong DB theo tên để lấy customer_id.
    - Tìm account_id bằng AccountService theo tên tài khoản hoặc phương thức thanh toán.
    - Kiểm tra các khoản nợ đang mở (status IN ('UNPAID', 'PARTIAL')) và kiểm tra số tiền thu.
    - Trả về waiting_confirmation để người dùng xác nhận trước khi thực hiện thu nợ.
    """
    missing_fields = validate(intent=intent, entities=entities)
    if missing_fields:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    customer_name = entities.get("customer") or entities.get("customer_name")
    if not customer_name:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["customer"],
            "message": "Thiếu thông tin khách hàng cần thu nợ"
        }

    raw_amount = (
        entities.get("price")
        or entities.get("amount")
        or entities.get("total_price")
    )
    if raw_amount is None:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["price"],
            "message": "Thiếu thông tin số tiền cần thu nợ"
        }

    try:
        amount = float(raw_amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return {
            "success": False,
            "status": "invalid_amount",
            "intent": intent,
            "message": "Số tiền thu nợ phải lớn hơn 0"
        }

    debt_id = entities.get("debt_id")
    customer_id = entities.get("customer_id")
    account_hint = (
        entities.get("account")
        or entities.get("account_name")
        or entities.get("payment")
    )

    db = get_db_session()
    try:
        # 1. Tìm customer_id nếu chưa có
        if not customer_id:
            db_customer = (
                db.query(Customer)
                .filter(
                    Customer.user_id == user_id,
                    Customer.customer_name.ilike(f"%{customer_name}%")
                )
                .first()
            )
            if not db_customer:
                return {
                    "success": False,
                    "status": "customer_not_found",
                    "intent": intent,
                    "customer_name": customer_name,
                    "message": f"Không tìm thấy khách hàng '{customer_name}' trong hệ thống."
                }
            customer_id = db_customer.customer_id
            customer_name = db_customer.customer_name

        # 2. Tìm account_id bằng AccountService
        account = AccountService.get_account_by_name(
            db=db,
            user_id=user_id,
            account_name=account_hint,
            fallback_to_default=True,
        )
        if not account:
            account = AccountService.get_or_create_account_by_name(
                db=db,
                user_id=user_id,
                account_name="Tiền mặt",
                account_type="CASH",
            )
        account_id = account.account_id
        account_name = account.account_name

        # 3. Kiểm tra công nợ đang mở
        if debt_id:
            debt = DebtRepository.get_debt_by_id_and_user(
                debt_id=int(debt_id),
                user_id=user_id,
                db=db,
                direction="RECEIVABLE"
            )
            if not debt:
                return {
                    "success": False,
                    "status": "debt_not_found",
                    "intent": intent,
                    "debt_id": debt_id,
                    "message": f"Khoản nợ #{debt_id} không tồn tại hoặc không thuộc về bạn."
                }
            rem = Decimal(str(debt.remaining_debt if debt.remaining_debt is not None else debt.original_amount))
            if Decimal(str(amount)) > rem:
                return {
                    "success": False,
                    "status": "overpayment",
                    "intent": intent,
                    "amount": amount,
                    "remaining_debt": float(rem),
                    "message": f"Số tiền thu ({amount:,.0f}đ) vượt quá số nợ còn lại ({float(rem):,.0f}đ) của khoản nợ #{debt_id}."
                }
        else:
            open_debts = DebtRepository.get_open_debts_by_customer_and_user(
                db=db,
                customer_id=customer_id,
                user_id=user_id,
                direction="RECEIVABLE",
            )
            if not open_debts:
                return {
                    "success": False,
                    "status": "no_open_debts",
                    "intent": intent,
                    "customer_name": customer_name,
                    "message": f"Khách hàng '{customer_name}' hiện không có khoản nợ nào đang mở."
                }
            total_remaining = sum(
                Decimal(str(d.remaining_debt if d.remaining_debt is not None else d.original_amount or 0))
                for d in open_debts
            )
            if Decimal(str(amount)) > total_remaining:
                return {
                    "success": False,
                    "status": "overpayment",
                    "intent": intent,
                    "amount": amount,
                    "total_remaining": float(total_remaining),
                    "message": (
                        f"Số tiền thu ({amount:,.0f}đ) vượt quá tổng số nợ hiện có "
                        f"({float(total_remaining):,.0f}đ) của khách hàng '{customer_name}'."
                    )
                }

    finally:
        db.close()

    payload = build_payload(intent=intent, entities=entities, text=text)
    payload["customer_id"] = customer_id
    payload["customer_name"] = customer_name
    payload["account_id"] = account_id
    payload["account_name"] = account_name
    payload["amount"] = amount
    if debt_id:
        payload["debt_id"] = int(debt_id)

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "thu_no_khach_hang",
        "payload": payload,
        "message": (
            f"Bạn có chắc muốn thu nợ từ khách hàng {customer_name} "
            f"số tiền {amount:,.0f}đ vào tài khoản '{account_name}' không?"
        )
    }


# ============================================================
# GHI NỢ NHÀ CUNG CẤP
# ============================================================

async def handle_ghi_no_nha_cung_cap(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    """
    Xử lý intent ghi nợ nhà cung cấp:
    - Tìm hoặc tự tạo Supplier trong DB nếu chưa có theo supplier_name.
    - Validate số tiền (hoặc tính từ sản phẩm x đơn giá x số lượng).
    - Trả về waiting_confirmation để người dùng xác nhận.
    """
    missing_fields = validate(intent=intent, entities=entities)
    if missing_fields:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    supplier_name = entities.get("supplier") or entities.get("supplier_name")
    if not supplier_name:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["supplier"],
            "message": "Thiếu thông tin nhà cung cấp cần ghi nợ"
        }

    product_name = entities.get("product")
    raw_qty = entities.get("quantity")
    raw_unit_price = entities.get("price") or entities.get("unit_price")
    raw_amount = (
        entities.get("original_amount")
        or entities.get("amount")
        or entities.get("total_price")
    )
    unit = entities.get("unit")

    try:
        qty = float(raw_qty) if raw_qty is not None else 1.0
    except (ValueError, TypeError):
        qty = 1.0

    unit_price = None
    if raw_unit_price is not None:
        try:
            unit_price = float(raw_unit_price)
        except (ValueError, TypeError):
            unit_price = None

    if raw_amount is not None:
        try:
            original_amount = float(raw_amount)
        except (ValueError, TypeError):
            original_amount = None
    elif product_name and unit_price is not None and unit_price > 0 and raw_qty is not None:
        original_amount = unit_price * qty
    elif unit_price is not None and unit_price > 0:
        original_amount = unit_price
    else:
        original_amount = None

    if original_amount is None or original_amount <= 0:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["price"],
            "message": "Thiếu thông tin số tiền nợ (hoặc sản phẩm và đơn giá)"
        }

    supplier_id = entities.get("supplier_id")
    if not supplier_id:
        db = get_db_session()
        try:
            db_supplier = (
                db.query(Supplier)
                .filter(
                    Supplier.user_id == user_id,
                    Supplier.supplier_name.ilike(f"%{supplier_name}%")
                )
                .first()
            )
            if not db_supplier:
                db_supplier = Supplier(
                    user_id=user_id,
                    supplier_name=supplier_name,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(db_supplier)
                db.commit()
                db.refresh(db_supplier)
            supplier_id = db_supplier.supplier_id
        finally:
            db.close()

    payload = build_payload(intent=intent, entities=entities, text=text)
    payload["supplier_id"] = supplier_id
    payload["supplier_name"] = supplier_name
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
        "action": "ghi_no_nha_cung_cap",
        "payload": payload,
        "message": (
            f"Bạn có chắc muốn ghi nợ cho nhà cung cấp {supplier_name} "
            f"số tiền {original_amount:,.0f}đ{detail_str} không?"
        )
    }


# ============================================================
# TRẢ NỢ / THU NỢ NHÀ CUNG CẤP
# ============================================================

async def handle_thu_no_nha_cung_cap(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    """
    Xử lý intent trả nợ / thu nợ nhà cung cấp:
    - Tìm nhà cung cấp trong DB theo tên để lấy supplier_id.
    - Tìm account_id nguồn trích tiền bằng AccountService (mặc định tiền mặt).
    - Kiểm tra các khoản nợ PAYABLE đang mở (status IN ('UNPAID', 'PARTIAL')).
    - Hỗ trợ nói 'trả hết'/'tất toán' -> amount = remaining_debt.
    - Trả về waiting_confirmation để người dùng xác nhận.
    """
    missing_fields = validate(intent=intent, entities=entities)
    if missing_fields:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    supplier_name = entities.get("supplier") or entities.get("supplier_name")
    if not supplier_name:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["supplier"],
            "message": "Thiếu thông tin nhà cung cấp cần trả nợ"
        }

    raw_amount = (
        entities.get("price")
        or entities.get("amount")
        or entities.get("total_price")
    )

    debt_id = entities.get("debt_id")
    supplier_id = entities.get("supplier_id")
    account_hint = (
        entities.get("account")
        or entities.get("account_name")
        or entities.get("payment")
    )

    is_settle_all = any(
        k in text.lower()
        for k in ("tất toán", "tat toan", "trả hết", "tra het", "thanh toán hết", "toàn bộ", "hết nợ", "trả sạch")
    )
    if raw_amount is None and not is_settle_all and not debt_id:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["price"],
            "message": "Thiếu thông tin số tiền cần trả nợ"
        }

    db = get_db_session()
    try:
        # 1. Tìm supplier_id nếu chưa có
        if not supplier_id:
            db_supplier = (
                db.query(Supplier)
                .filter(
                    Supplier.user_id == user_id,
                    Supplier.supplier_name.ilike(f"%{supplier_name}%")
                )
                .first()
            )
            if not db_supplier:
                return {
                    "success": False,
                    "status": "supplier_not_found",
                    "intent": intent,
                    "supplier_name": supplier_name,
                    "message": f"Không tìm thấy nhà cung cấp '{supplier_name}' trong hệ thống."
                }
            supplier_id = db_supplier.supplier_id
            supplier_name = db_supplier.supplier_name

        # 2. Tìm account_id bằng AccountService
        account = AccountService.get_account_by_name(
            db=db,
            user_id=user_id,
            account_name=account_hint,
            fallback_to_default=True,
        )
        if not account:
            account = AccountService.get_or_create_account_by_name(
                db=db,
                user_id=user_id,
                account_name="Tiền mặt",
                account_type="CASH",
            )
        account_id = account.account_id
        account_name = account.account_name

        # 3. Kiểm tra công nợ PAYABLE đang mở
        if debt_id:
            debt = DebtRepository.get_debt_by_id_and_user(
                debt_id=int(debt_id),
                user_id=user_id,
                db=db,
                direction="PAYABLE"
            )
            if not debt:
                return {
                    "success": False,
                    "status": "debt_not_found",
                    "intent": intent,
                    "debt_id": debt_id,
                    "message": f"Khoản nợ #{debt_id} không tồn tại hoặc không thuộc về bạn."
                }
            rem = Decimal(str(debt.remaining_debt if debt.remaining_debt is not None else debt.original_amount))
            if raw_amount is None:
                amount = float(rem)
            else:
                try:
                    amount = float(raw_amount)
                    if amount <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "status": "invalid_amount",
                        "intent": intent,
                        "message": "Số tiền trả nợ phải lớn hơn 0"
                    }
                if Decimal(str(amount)) > rem:
                    return {
                        "success": False,
                        "status": "overpayment",
                        "intent": intent,
                        "amount": amount,
                        "remaining_debt": float(rem),
                        "message": f"Số tiền trả ({amount:,.0f}đ) vượt quá số nợ còn lại ({float(rem):,.0f}đ) của khoản nợ #{debt_id}."
                    }
        else:
            open_debts = DebtRepository.get_open_debts_by_supplier_and_user(
                db=db,
                supplier_id=supplier_id,
                user_id=user_id,
                direction="PAYABLE",
            )
            if not open_debts:
                return {
                    "success": False,
                    "status": "no_open_debts",
                    "intent": intent,
                    "supplier_name": supplier_name,
                    "message": f"Nhà cung cấp '{supplier_name}' hiện không có khoản nợ nào cần trả."
                }
            total_remaining = sum(
                Decimal(str(d.remaining_debt if d.remaining_debt is not None else d.original_amount or 0))
                for d in open_debts
            )
            if raw_amount is None:
                amount = float(total_remaining)
            else:
                try:
                    amount = float(raw_amount)
                    if amount <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "status": "invalid_amount",
                        "intent": intent,
                        "message": "Số tiền trả nợ phải lớn hơn 0"
                    }
                if Decimal(str(amount)) > total_remaining:
                    return {
                        "success": False,
                        "status": "overpayment",
                        "intent": intent,
                        "amount": amount,
                        "total_remaining": float(total_remaining),
                        "message": (
                            f"Số tiền trả ({amount:,.0f}đ) vượt quá tổng số nợ hiện có "
                            f"({float(total_remaining):,.0f}đ) của nhà cung cấp '{supplier_name}'."
                        )
                    }

    finally:
        db.close()

    payload = build_payload(intent=intent, entities=entities, text=text)
    payload["supplier_id"] = supplier_id
    payload["supplier_name"] = supplier_name
    payload["account_id"] = account_id
    payload["account_name"] = account_name
    payload["amount"] = amount
    if debt_id:
        payload["debt_id"] = int(debt_id)

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "thu_no_nha_cung_cap",
        "payload": payload,
        "message": (
            f"Bạn có chắc muốn trả nợ cho nhà cung cấp {supplier_name} "
            f"số tiền {amount:,.0f}đ từ tài khoản '{account_name}' không?"
        )
    }





