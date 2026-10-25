from decimal import Decimal
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from app.repositories.inventory_repo import InventoryRepository
from app.services.debt_service import DebtService
from app.models.intent_model import Intent
from app.repositories.inventory.inventory_lookup_repo import AmbiguousMatchError
from app.services.sales_policy import (
    STRICT,
    MADE_TO_ORDER,
    RAW_MATERIAL_BLOCKED,
    ERROR_INSUFFICIENT_STOCK,
    ERROR_CANNOT_SELL_RAW_MATERIAL,
    get_sale_stock_policy,
    get_user_business_type,
    normalize_product_type,
    is_unpaid_payment,
)


class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepository(db)

    def _normalize_payload_items(
        self, user_id: int, payload: Dict[str, Any], is_import: bool = False, **kwargs
    ) -> List[Dict[str, Any]]:
        raw_items = payload.get("items") or payload.get("products") or []

        # Tự đóng gói thành list nếu payload gửi dạng item đơn lẻ
        if not raw_items:
            product_identifier = payload.get("product_name") or payload.get("product") or payload.get("product_id")
            if product_identifier:
                raw_items = [{
                    "product_id": payload.get("product_id"),
                    "product_name": payload.get("product_name") or payload.get("product"),
                    "quantity": payload.get("quantity", 1),
                    "unit": payload.get("unit", ""),
                    "unit_price": payload.get("unit_price") if payload.get("unit_price") is not None else payload.get("price")
                }]

        normalized_items = []
        for item in raw_items:
            p_id = item.get("product_id")
            p_name = item.get("product_name") or item.get("product")

            # 1. Tìm product_id thông qua Repo nếu thiếu ID
            if not p_id and p_name:
                p_id = self.repo.get_product_id_by_name(user_id=user_id, name=p_name)
                if not p_id:
                    raise ValueError(f"Không tìm thấy sản phẩm '{p_name}' trong hệ thống.")

            # 2. Lấy Object Product từ DB để truy xuất giá & đơn vị mặc định
            product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=p_id)
            if not product_obj:
                raise ValueError(f"Sản phẩm (ID: {p_id}) không tồn tại hoặc không thuộc quyền sở hữu của bạn.")
            if getattr(product_obj, "is_active", True) is False:
                raise ValueError(f"Sản phẩm '{product_obj.product_name}' đã ngừng kinh doanh.")

            # Validate quantity > 0
            raw_qty = item.get("quantity")
            try:
                qty_val = float(raw_qty) if raw_qty is not None else 1.0
                if qty_val <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(f"Số lượng sản phẩm '{p_name or p_id}' phải lớn hơn 0.")

            # 3. Lấy đơn giá người dùng nhập
            input_price = item.get("unit_price") if item.get("unit_price") is not None else item.get("price")
            final_unit_price = None

            # TH1: Có giá người dùng nhập vào (> 0)
            if input_price is not None and float(input_price) > 0:
                final_unit_price = Decimal(str(input_price))
            else:
                # TH2: Tự lấy unit_price từ bảng Product
                if hasattr(self.repo, "get_product_price"):
                    final_unit_price = self.repo.get_product_price(user_id=user_id, product_id=p_id)
                elif product_obj and getattr(product_obj, "unit_price", None) is not None:
                    final_unit_price = Decimal(str(product_obj.unit_price))

            # TH3: Cả người dùng không nhập VÀ trong DB unit_price bị Null/0
            if not final_unit_price or final_unit_price <= 0:
                display_name = (
                    getattr(product_obj, "product_name", None)
                    or getattr(product_obj, "name", None)
                    or p_name
                    or f"ID {p_id}"
                )
                raise ValueError(f"Sản phẩm '{display_name}' chưa có giá trong hệ thống. Vui lòng bổ sung giá.")

            # 4. Xác định đơn vị tính (Ưu tiên: Payload -> DB default_unit)
            unit = item.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")

            normalized_items.append({
                "product_id": p_id,
                "product_name": (
                    getattr(product_obj, "product_name", None)
                    or getattr(product_obj, "name", None)
                    or p_name
                    or ""
                ),
                "quantity": qty_val,
                "unit": unit,
                "unit_price": final_unit_price,
                "product_type": normalize_product_type(getattr(product_obj, "product_type", None)),
            })

        return normalized_items

    def import_goods(self, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thực hiện nghiệp vụ nhập hàng (Import Goods Transaction)
        """
        try:
            items = self._normalize_payload_items(user_id, payload, is_import=True)
            if not items:
                return {
                    "status": "error",
                    "success": False,
                    "message": "Danh sách sản phẩm nhập không được rỗng."
                }

            # 1. Tính tổng giá trị đơn hàng
            total_amount = Decimal("0.0")
            processed_items = []

            for item in items:
                qty = Decimal(str(item["quantity"]))
                price = Decimal(str(item["unit_price"]))
                subtotal = qty * price
                total_amount += subtotal
                
                pname = item.get("product_name") or item.get("name")
                if not pname:
                    prod_obj = self.repo.get_product_by_id(user_id, item["product_id"])
                    if prod_obj:
                        pname = prod_obj.product_name

                processed_items.append({
                    "product_id": item["product_id"],
                    "product_name": pname,
                    "quantity": qty,
                    "unit": item.get("unit", ""),
                    "unit_price": price,
                    "subtotal": subtotal
                })

            # Xử lý payment_status & amount_paid
            is_unpaid = is_unpaid_payment(payload.get("payment_status"))

            amount_paid_input = payload.get("amount_paid")
            if amount_paid_input is not None:
                amount_paid = Decimal(str(amount_paid_input))
            elif is_unpaid:
                amount_paid = Decimal("0.0")
            else:
                amount_paid = total_amount

            # Chuẩn hóa payment_status theo enum ERD: 'PAID', 'PARTIAL', 'PENDING'
            if amount_paid >= total_amount:
                payment_status_str = "PAID"
            elif amount_paid > 0:
                payment_status_str = "PARTIAL"
            else:
                payment_status_str = "PENDING"

            # Xử lý supplier_id & supplier_name (Chỉ tìm kiếm trong DB, KHÔNG tự ý tạo mới Supplier)
            supplier_id = payload.get("supplier_id")
            supplier_name = payload.get("supplier_name") or payload.get("supplier")
            
            if not supplier_id and supplier_name:
                existing_supplier = self.repo.get_supplier_by_name(user_id=user_id, name=str(supplier_name))
                if existing_supplier:
                    supplier_id = existing_supplier.supplier_id
                else:
                    return {
                        "status": "error",
                        "success": False,
                        "message": f"Không tìm thấy nhà cung cấp '{supplier_name}' trong hệ thống. Vui lòng tạo nhà cung cấp trước."
                    }

            unpaid_amount = total_amount - amount_paid

            # Nếu phát sinh nợ nhưng không có nhà cung cấp -> Báo lỗi cần nhà cung cấp để ghi nợ
            if unpaid_amount > 0 and not supplier_id:
                return {
                    "status": "error",
                    "success": False,
                    "message": "Đơn hàng chưa thanh toán đủ cần có thông tin Nhà cung cấp để ghi nợ."
                }

            account_id = payload.get("account_id")

            # Lấy intent_id nếu tồn tại trong DB
            intent_obj = self.db.query(Intent).filter(Intent.intent_name.in_(["mua_hang", "nhap_hang"])).first()
            intent_id = intent_obj.intent_id if intent_obj else None

            # 2. Tạo Master Transaction
            tx = self.repo.create_transaction(
                user_id=user_id,
                supplier_id=supplier_id,
                account_id=account_id,
                total_amount=total_amount,
                payment_status=payment_status_str,
                input_method=payload.get("input_method", "MANUAL"),
                input_text=payload.get("input_text"),
                note=payload.get("note") or payload.get("input_text"),
                intent_id=intent_id,
            )

            # 3. Tạo Transaction Details & Cập nhật biến động Kho
            for item in processed_items:
                self.repo.create_transaction_detail(
                    transaction_id=tx.transaction_id,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    unit=item["unit"],
                    unit_price=item["unit_price"],
                    subtotal=item["subtotal"],
                    product_name=item.get("product_name"),
                )

                # Khóa dòng sản phẩm để tồn kho đọc ra không bị lệch khi có giao dịch đồng thời
                self.repo.lock_product(user_id, item["product_id"])
                qty_before = self.repo.get_latest_stock(user_id, item["product_id"])
                qty_after = qty_before + item["quantity"]

                self.repo.create_inventory_transaction(
                    user_id=user_id,
                    product_id=item["product_id"],
                    transaction_id=tx.transaction_id,
                    type="IN",
                    quantity=item["quantity"],
                    unit=item["unit"],
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    note=f"Nhập hàng theo giao dịch #{tx.transaction_id}",
                )

            # 4. Trừ tiền tài khoản thanh toán
            if account_id and amount_paid > 0:
                if hasattr(self.repo, "increase_account_balance"):
                    self.repo.increase_account_balance(user_id=user_id, account_id=account_id, amount=-amount_paid)
                elif hasattr(self.repo, "update_account_balance"):
                    self.repo.update_account_balance(account_id=account_id, amount=amount_paid)

            # 5. Xử lý ghi nợ nhà cung cấp (PAYABLE) qua DebtService
            created_debt = None
            if unpaid_amount > 0 and supplier_id:
                debt_status = "PARTIAL" if amount_paid > 0 else "UNPAID"
                created_debt = DebtService.create_payable_debt_for_transaction(
                    db=self.db,
                    user_id=user_id,
                    supplier_id=supplier_id,
                    transaction_id=tx.transaction_id,
                    amount=unpaid_amount,
                    status=debt_status,
                    flush_only=True,
                )

            self.db.commit()
            self.db.refresh(tx)

            return {
                "status": "success",
                "success": True,
                "message": "Nhập hàng thành công",
                "transaction_id": tx.transaction_id,
                "total_amount": float(total_amount),
                "quantity": float(sum([item["quantity"] for item in processed_items])),
                "amount_paid": float(amount_paid),
                "remaining_debt": float(unpaid_amount) if unpaid_amount > 0 else 0.0,
                "supplier_id": supplier_id,
                "debt_id": getattr(created_debt, "debt_id", None) if created_debt else None,
                "supplier_debt": float(unpaid_amount) if unpaid_amount > 0 else 0.0
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi xử lý nhập hàng: {str(e)}"
            }

    def sell_goods(self, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thực hiện nghiệp vụ bán hàng (Sale Goods Transaction)
        """
        try:
            items = self._normalize_payload_items(user_id, payload, is_import=False)
            if not items:
                return {
                    "status": "error",
                    "success": False,
                    "message": "Danh sách sản phẩm bán không được rỗng."
                }

            # 1. Áp dụng quy tắc business_type/product_type, kiểm tra tồn kho & tính tổng tiền
            business_type = get_user_business_type(self.db, user_id)
            total_amount = Decimal("0.0")
            processed_items = []

            # Khóa theo thứ tự product_id tăng dần để tránh deadlock khi 2 đơn cùng chứa nhiều sản phẩm
            for item in sorted(items, key=lambda it: it["product_id"]):
                self.repo.lock_product(user_id, item["product_id"])

            for item in items:
                qty = Decimal(str(item["quantity"]))
                product_id = item["product_id"]
                price = Decimal(str(item["unit_price"]))
                display_name = item.get("product_name") or product_id
                policy = get_sale_stock_policy(business_type, item.get("product_type"))

                if policy == RAW_MATERIAL_BLOCKED:
                    self.db.rollback()
                    return {
                        "status": ERROR_CANNOT_SELL_RAW_MATERIAL,
                        "error_code": ERROR_CANNOT_SELL_RAW_MATERIAL,
                        "success": False,
                        "message": f"Sản phẩm '{display_name}' là nguyên liệu sản xuất (RAW_MATERIAL), không thể bán trực tiếp."
                    }

                current_stock = self.repo.get_latest_stock(user_id, product_id)
                if policy == STRICT and current_stock < qty:
                    self.db.rollback()
                    return {
                        "status": "out_of_stock",
                        "error_code": ERROR_INSUFFICIENT_STOCK,
                        "success": False,
                        "message": f"Sản phẩm '{display_name}' không đủ tồn kho (Tồn: {current_stock}, Yêu cầu: {qty})"
                    }

                # Số lượng thực trừ kho:
                # - STRICT: trừ đủ số bán
                # - MADE_TO_ORDER: chỉ trừ phần thành phẩm đang có sẵn, phần còn lại làm theo yêu cầu (không âm kho)
                # - NO_INVENTORY: dịch vụ, không trừ kho
                if policy == STRICT:
                    stock_out_qty = qty
                elif policy == MADE_TO_ORDER:
                    stock_out_qty = min(qty, max(current_stock, Decimal("0")))
                else:
                    stock_out_qty = Decimal("0")

                subtotal = qty * price
                total_amount += subtotal

                pname = item.get("product_name") or item.get("name")
                if not pname:
                    prod_obj = self.repo.get_product_by_id(user_id, product_id)
                    if prod_obj:
                        pname = prod_obj.product_name

                processed_items.append({
                    "product_id": product_id,
                    "product_name": pname,
                    "quantity": qty,
                    "unit": item.get("unit", ""),
                    "unit_price": price,
                    "subtotal": subtotal,
                    "stock_before": current_stock,
                    "stock_out_qty": stock_out_qty,
                })

            # Xử lý payment_status & amount_paid
            is_unpaid = is_unpaid_payment(payload.get("payment_status"))

            amount_paid_input = payload.get("amount_paid")
            if amount_paid_input is not None:
                amount_paid = Decimal(str(amount_paid_input))
            elif is_unpaid:
                amount_paid = Decimal("0.0")
            else:
                amount_paid = total_amount

            # Chuẩn hóa payment_status theo enum ERD: 'PAID', 'PARTIAL', 'PENDING'
            if amount_paid >= total_amount:
                payment_status_str = "PAID"
            elif amount_paid > 0:
                payment_status_str = "PARTIAL"
            else:
                payment_status_str = "PENDING"

            # Xử lý customer_id & customer_name (Chỉ tìm kiếm trong DB Customer, KHÔNG tự ý tạo mới Customer)
            customer_id = payload.get("customer_id")
            customer_name = payload.get("customer_name") or payload.get("customer")

            if not customer_id and customer_name:
                existing_customer = self.repo.get_customer_by_name(user_id=user_id, name=str(customer_name))
                if existing_customer:
                    customer_id = existing_customer.customer_id
                else:
                    return {
                        "status": "error",
                        "success": False,
                        "message": f"Không tìm thấy khách hàng '{customer_name}' trong hệ thống. Vui lòng tạo khách hàng trước."
                    }

            unpaid_amount = total_amount - amount_paid

            # Nếu phát sinh nợ nhưng không có khách hàng -> Báo lỗi cần khách hàng để ghi nợ
            if unpaid_amount > 0 and not customer_id:
                return {
                    "status": "error",
                    "success": False,
                    "message": "Đơn hàng bán chưa thanh toán đủ cần có thông tin Khách hàng để ghi nợ."
                }

            account_id = payload.get("account_id")

            # Lấy intent_id nếu tồn tại trong DB
            intent_obj = self.db.query(Intent).filter(Intent.intent_name == "ban_hang").first()
            intent_id = intent_obj.intent_id if intent_obj else None

            # 2. Tạo Master Transaction
            tx = self.repo.create_sale_transaction(
                user_id=user_id,
                customer_id=customer_id,
                account_id=account_id,
                total_amount=total_amount,
                payment_status=payment_status_str,
                input_method=payload.get("input_method", "MANUAL"),
                input_text=payload.get("input_text"),
                note=payload.get("note") or payload.get("input_text"),
                intent_id=intent_id,
            )

            # 3. Tạo Transaction Details & Trừ Kho
            for item in processed_items:
                self.repo.create_transaction_detail(
                    transaction_id=tx.transaction_id,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    unit=item["unit"],
                    unit_price=item["unit_price"],
                    subtotal=item["subtotal"],
                    product_name=item.get("product_name"),
                )
                if item["stock_out_qty"] <= 0:
                    continue

                qty_before = item["stock_before"]
                qty_after = qty_before - item["stock_out_qty"]

                self.repo.create_inventory_transaction(
                    user_id=user_id,
                    product_id=item["product_id"],
                    transaction_id=tx.transaction_id,
                    type="OUT",
                    quantity=item["stock_out_qty"],
                    unit=item["unit"],
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    note=f"Bán hàng theo giao dịch #{tx.transaction_id}",
                )

            # 4. Cộng tiền vào Tài khoản thu tiền
            if account_id and amount_paid > 0:
                self.repo.increase_account_balance(
                    user_id=user_id, account_id=account_id, amount=amount_paid
                )

            # 5. Ghi nhận nợ phải thu (RECEIVABLE) qua DebtService
            created_debt = None
            if unpaid_amount > 0 and customer_id:
                debt_status = "PARTIAL" if amount_paid > 0 else "UNPAID"
                created_debt = DebtService.create_receivable_debt_for_transaction(
                    db=self.db,
                    user_id=user_id,
                    customer_id=customer_id,
                    transaction_id=tx.transaction_id,
                    amount=unpaid_amount,
                    status=debt_status,
                    flush_only=True,
                )

            self.db.commit()
            self.db.refresh(tx)

            # Kích hoạt cảnh báo tồn kho nếu hàng đã bán hết hoặc dưới min_quantity
            for item in processed_items:
                if item["stock_out_qty"] <= 0:
                    continue
                try:
                    from app.services.stock_alert_service import StockAlertService
                    StockAlertService.check_and_notify_stock(
                        db=self.db,
                        user_id=user_id,
                        product_id=item["product_id"],
                        current_stock=item["stock_before"] - item["stock_out_qty"]
                    )
                except Exception:
                    pass

            return {
                "status": "success",
                "success": True,
                "message": "Bán hàng thành công",
                "transaction_id": tx.transaction_id,
                "total_amount": float(total_amount),
                "quantity": float(sum([item["quantity"] for item in processed_items])),
                "amount_paid": float(amount_paid),
                "remaining_debt": float(unpaid_amount) if unpaid_amount > 0 else 0.0,
                "customer_id": customer_id,
                "debt_id": getattr(created_debt, "debt_id", None) if created_debt else None,
                "customer_debt": float(unpaid_amount) if unpaid_amount > 0 else 0.0,
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi xử lý bán hàng: {str(e)}"
            }
            
    def check_stock(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name")

            if not product_id and product_name:
                try:
                    product_id = self.repo.get_product_id_by_name(
                        user_id=user_id,
                        name=product_name
                    )
                except AmbiguousMatchError as amb:
                    return {
                        "status": "ambiguous_product",
                        "success": False,
                        "candidates": amb.candidates,
                        "message": str(amb)
                    }

            if not product_id:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm '{product_name}'."
                }

            product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=product_id)
            if not product_obj:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm hoặc sản phẩm không thuộc quyền sở hữu (ID: {product_id})."
                }
            if getattr(product_obj, "is_active", True) is False:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Sản phẩm '{product_obj.product_name}' đã ngừng kinh doanh."
                }

            stock = self.repo.get_latest_stock(
                user_id=user_id,
                product_id=product_id
            )

            unit_price = 0.0
            default_unit = ""
            if hasattr(product_obj, "unit_price") and product_obj.unit_price is not None:
                try:
                    unit_price = float(product_obj.unit_price)
                except (ValueError, TypeError):
                    unit_price = 0.0
            elif hasattr(product_obj, "price") and product_obj.price is not None:
                try:
                    unit_price = float(product_obj.price)
                except (ValueError, TypeError):
                    unit_price = 0.0

            if hasattr(product_obj, "default_unit") and product_obj.default_unit is not None:
                default_unit = str(product_obj.default_unit)
            elif hasattr(product_obj, "unit") and product_obj.unit is not None:
                default_unit = str(product_obj.unit)

            actual_product_name = (
                getattr(product_obj, "product_name", None)
                or getattr(product_obj, "name", None)
                or product_name
                or ""
            )

            return {
                "status": "success",
                "success": True,
                "message": f"Sản phẩm '{actual_product_name}' còn {stock}.",
                "product_id": product_id,
                "product_name": actual_product_name,
                "quantity": float(stock),
                "unit_price": unit_price,
                "default_unit": default_unit,
                "product_type": normalize_product_type(getattr(product_obj, "product_type", None)),
                "business_type": get_user_business_type(self.db, user_id),
            }

        except Exception as e:
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi kiểm tra tồn kho: {str(e)}"
            }

    def nhap_kho(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ nhập kho đơn thuần (Inventory IN).
        Mapping theo Intent_DB_Mapping.docx: Inventory_Transaction + Product.
        TUYỆT ĐỐI KHÔNG tạo: Customer, Supplier, Debt, Sales/Purchase Transaction.
        """
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name") or payload.get("product")
            quantity_raw = payload.get("quantity")

            if quantity_raw is None or quantity_raw == "":
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["quantity"],
                    "message": "Thiếu thông tin số lượng cần nhập kho."
                }

            try:
                qty = Decimal(str(quantity_raw))
                if qty <= 0:
                    return {
                        "status": "error",
                        "success": False,
                        "message": "Số lượng nhập kho phải lớn hơn 0."
                    }
            except Exception:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Số lượng không hợp lệ: {quantity_raw}"
                }

            # 1. Tìm product_id thông qua Repo nếu thiếu ID
            if not product_id and product_name:
                product_id = self.repo.get_product_id_by_name(user_id=user_id, name=str(product_name))
                if not product_id:
                    return {
                        "status": "error",
                        "success": False,
                        "missing_fields": ["product"],
                        "message": f"Không tìm thấy sản phẩm '{product_name}' trong hệ thống."
                    }
            elif not product_id and not product_name:
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["product"],
                    "message": "Thiếu thông tin sản phẩm cần nhập kho."
                }

            # Khóa dòng sản phẩm (chống race condition) và chỉ cho thao tác trên sản phẩm của chính user
            product_obj = self.repo.lock_product(user_id=user_id, product_id=product_id)
            if not product_obj:
                self.db.rollback()
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm hoặc sản phẩm không thuộc quyền sở hữu (ID: {product_id})."
                }
            if getattr(product_obj, "is_active", True) is False:
                self.db.rollback()
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Sản phẩm '{product_obj.product_name}' đã ngừng kinh doanh."
                }
            unit = payload.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")
            actual_product_name = product_name or (getattr(product_obj, "product_name", "") if product_obj else f"ID {product_id}")

            # 2. Cập nhật tồn kho qua InventoryTransaction
            qty_before = self.repo.get_latest_stock(user_id, product_id)
            qty_after = qty_before + qty

            inv_tx = self.repo.create_inventory_transaction(
                user_id=user_id,
                product_id=product_id,
                transaction_id=None,
                type="IN",
                quantity=qty,
                unit=unit,
                quantity_before=qty_before,
                quantity_after=qty_after,
                note=payload.get("note") or payload.get("input_text") or "Nhập kho",
            )

            self.db.commit()
            self.db.refresh(inv_tx)

            return {
                "status": "success",
                "success": True,
                "message": f"Nhập kho thành công {qty} {unit} {actual_product_name}.",
                "inventory_transaction_id": inv_tx.inventory_transaction_id,
                "product_id": product_id,
                "product_name": actual_product_name,
                "quantity": float(qty),
                "unit": unit,
                "quantity_before": float(qty_before),
                "quantity_after": float(qty_after),
                "inventory_type": "IN"
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi xử lý nhập kho: {str(e)}"
            }

    def xuat_kho(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ xuất kho đơn thuần (Inventory OUT).
        Mapping theo Intent_DB_Mapping.docx: Inventory_Transaction + Product.
        TUYỆT ĐỐI KHÔNG tạo: Customer, Supplier, Debt, Sales/Purchase Transaction.
        Phải kiểm tra tồn kho, không cho phép xuất vượt quá số lượng tồn.
        """
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name") or payload.get("product")
            quantity_raw = payload.get("quantity")

            if quantity_raw is None or quantity_raw == "":
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["quantity"],
                    "message": "Thiếu thông tin số lượng cần xuất kho."
                }

            try:
                qty = Decimal(str(quantity_raw))
                if qty <= 0:
                    return {
                        "status": "error",
                        "success": False,
                        "message": "Số lượng xuất kho phải lớn hơn 0."
                    }
            except Exception:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Số lượng không hợp lệ: {quantity_raw}"
                }

            # 1. Tìm product_id thông qua Repo nếu thiếu ID
            if not product_id and product_name:
                product_id = self.repo.get_product_id_by_name(user_id=user_id, name=str(product_name))
                if not product_id:
                    return {
                        "status": "error",
                        "success": False,
                        "missing_fields": ["product"],
                        "message": f"Không tìm thấy sản phẩm '{product_name}' trong hệ thống."
                    }
            elif not product_id and not product_name:
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["product"],
                    "message": "Thiếu thông tin sản phẩm cần xuất kho."
                }

            # Khóa dòng sản phẩm (chống race condition) và chỉ cho thao tác trên sản phẩm của chính user
            product_obj = self.repo.lock_product(user_id=user_id, product_id=product_id)
            if not product_obj:
                self.db.rollback()
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm hoặc sản phẩm không thuộc quyền sở hữu (ID: {product_id})."
                }
            if getattr(product_obj, "is_active", True) is False:
                self.db.rollback()
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Sản phẩm '{product_obj.product_name}' đã ngừng kinh doanh."
                }
            unit = payload.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")
            actual_product_name = product_name or (getattr(product_obj, "product_name", "") if product_obj else f"ID {product_id}")

            # 2. Kiểm tra số lượng tồn kho
            qty_before = self.repo.get_latest_stock(user_id, product_id)
            if qty_before < qty:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Sản phẩm '{actual_product_name}' không đủ tồn kho (Tồn: {qty_before}, Yêu cầu: {qty})"
                }

            qty_after = qty_before - qty

            inv_tx = self.repo.create_inventory_transaction(
                user_id=user_id,
                product_id=product_id,
                transaction_id=None,
                type="OUT",
                quantity=qty,
                unit=unit,
                quantity_before=qty_before,
                quantity_after=qty_after,
                note=payload.get("note") or payload.get("input_text") or "Xuất kho",
            )

            self.db.commit()
            self.db.refresh(inv_tx)

            # Kích hoạt cảnh báo tồn kho nếu hết hàng hoặc dưới min_quantity
            try:
                from app.services.stock_alert_service import StockAlertService
                StockAlertService.check_and_notify_stock(
                    db=self.db,
                    user_id=user_id,
                    product_id=product_id,
                    current_stock=qty_after
                )
            except Exception:
                pass

            return {
                "status": "success",
                "success": True,
                "message": f"Xuất kho thành công {qty} {unit} {actual_product_name}.",
                "inventory_transaction_id": inv_tx.inventory_transaction_id,
                "product_id": product_id,
                "product_name": actual_product_name,
                "quantity": float(qty),
                "unit": unit,
                "quantity_before": float(qty_before),
                "quantity_after": float(qty_after),
                "inventory_type": "OUT"
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi xử lý xuất kho: {str(e)}"
            }

    def report_damage(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Báo hàng hư hỏng / hết hạn: tạo Inventory_Transaction loại DAMAGE và trừ tồn kho.
        Không tạo Transaction tài chính, không được làm tồn kho âm.
        """
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name") or payload.get("product")

            try:
                qty = Decimal(str(payload.get("quantity")))
            except Exception:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Số lượng không hợp lệ: {payload.get('quantity')}"
                }
            if qty <= 0:
                return {
                    "status": "error",
                    "success": False,
                    "message": "Số lượng hàng hỏng phải lớn hơn 0."
                }

            if not product_id and product_name:
                product_id = self.repo.get_product_id_by_name(user_id=user_id, name=str(product_name))
            if not product_id:
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["product"],
                    "message": f"Không tìm thấy sản phẩm '{product_name}' trong hệ thống."
                }

            product_obj = self.repo.lock_product(user_id=user_id, product_id=product_id)
            if not product_obj:
                self.db.rollback()
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm hoặc sản phẩm không thuộc quyền sở hữu (ID: {product_id})."
                }

            unit = payload.get("unit") or product_obj.default_unit or ""
            qty_before = self.repo.get_latest_stock(user_id, product_id)
            if qty_before < qty:
                self.db.rollback()
                return {
                    "status": "out_of_stock",
                    "error_code": ERROR_INSUFFICIENT_STOCK,
                    "success": False,
                    "message": f"Sản phẩm '{product_obj.product_name}' chỉ còn {qty_before}, không thể báo hỏng {qty}."
                }
            qty_after = qty_before - qty

            inv_tx = self.repo.create_inventory_transaction(
                user_id=user_id,
                product_id=product_id,
                transaction_id=None,
                type="DAMAGE",
                quantity=qty,
                unit=unit,
                quantity_before=qty_before,
                quantity_after=qty_after,
                note=payload.get("note") or payload.get("input_text") or "Hàng hư hỏng",
            )

            self.db.commit()
            self.db.refresh(inv_tx)

            try:
                from app.services.stock_alert_service import StockAlertService
                StockAlertService.check_and_notify_stock(
                    db=self.db,
                    user_id=user_id,
                    product_id=product_id,
                    current_stock=qty_after
                )
            except Exception:
                pass

            return {
                "status": "success",
                "success": True,
                "message": f"Đã ghi nhận {qty} {unit} {product_obj.product_name} bị hư hỏng.",
                "inventory_transaction_id": inv_tx.inventory_transaction_id,
                "product_id": product_id,
                "product_name": product_obj.product_name,
                "quantity": float(qty),
                "unit": unit,
                "quantity_before": float(qty_before),
                "quantity_after": float(qty_after),
                "inventory_type": "DAMAGE"
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi ghi nhận hàng hư hỏng: {str(e)}"
            }

    # Alias phương thức
    process_export = sell_goods
    process_import = import_goods
    process_check_stock = check_stock
    process_nhap_kho = nhap_kho
    process_xuat_kho = xuat_kho