from decimal import Decimal
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from app.repositories.inventory_repo import InventoryRepository


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
                display_name = p_name or (getattr(product_obj, "name", None) if product_obj else f"ID {p_id}")
                raise ValueError(f"Sản phẩm '{display_name}' chưa có giá trong hệ thống. Vui lòng bổ sung giá.")

            # 4. Xác định đơn vị tính (Ưu tiên: Payload -> DB default_unit)
            unit = item.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")

            normalized_items.append({
                "product_id": p_id,
                "product_name": p_name or (getattr(product_obj, "name", "") if product_obj else ""),
                "quantity": item.get("quantity", 1),
                "unit": unit,
                "unit_price": final_unit_price
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
                
                processed_items.append({
                    "product_id": item["product_id"],
                    "quantity": qty,
                    "unit": item.get("unit", ""),
                    "unit_price": price,
                    "subtotal": subtotal
                })

            amount_paid_input = payload.get("amount_paid")
            amount_paid = Decimal(str(amount_paid_input)) if amount_paid_input is not None else total_amount
            supplier_id = payload.get("supplier_id")
            account_id = payload.get("account_id")

            # Nhận trực tiếp trạng thái thanh toán bằng tiếng Anh (Mặc định là "PAID" nếu không truyền)
            payment_status_str = payload.get("payment_status") or "PAID"

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
                )

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

            # 5. Xử lý ghi nợ
            unpaid_amount = total_amount - amount_paid
            if unpaid_amount > 0 and supplier_id:
                debt_status = "PARTIAL" if amount_paid > 0 else "UNPAID"
                if hasattr(self.repo, "create_payable_debt"):
                    self.repo.create_payable_debt(
                        transaction_id=tx.transaction_id,
                        user_id=user_id,
                        supplier_id=supplier_id,
                        amount=unpaid_amount,
                        status=debt_status
                    )
                elif hasattr(self.repo, "create_debt"):
                    self.repo.create_debt(
                        transaction_id=tx.transaction_id,
                        user_id=user_id,
                        supplier_id=supplier_id,
                        amount=unpaid_amount,
                        status=debt_status
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
                "remaining_debt": float(unpaid_amount) if unpaid_amount > 0 else 0.0
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

            # 1. Kiểm tra tồn kho & Tính tổng tiền đơn hàng
            total_amount = Decimal("0.0")
            processed_items = []

            for item in items:
                qty = Decimal(str(item["quantity"]))
                product_id = item["product_id"]
                price = Decimal(str(item["unit_price"]))

                current_stock = self.repo.get_latest_stock(user_id, product_id)
                if current_stock < qty:
                    return {
                        "status": "error",
                        "success": False,
                        "message": f"Sản phẩm '{item.get('product_name', product_id)}' không đủ tồn kho (Tồn: {current_stock}, Yêu cầu: {qty})"
                    }

                subtotal = qty * price
                total_amount += subtotal

                processed_items.append({
                    "product_id": product_id,
                    "quantity": qty,
                    "unit": item.get("unit", ""),
                    "unit_price": price,
                    "subtotal": subtotal,
                    "stock_before": current_stock,
                })

            amount_paid_input = payload.get("amount_paid")
            amount_paid = Decimal(str(amount_paid_input)) if amount_paid_input is not None else total_amount
            customer_id = payload.get("customer_id")
            account_id = payload.get("account_id")

            # Nhận trực tiếp trạng thái thanh toán bằng tiếng Anh (Mặc định là "PAID" nếu không truyền)
            payment_status_str = payload.get("payment_status") or "PAID"

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
                )
                qty_before = item["stock_before"]
                qty_after = qty_before - item["quantity"]

                self.repo.create_inventory_transaction(
                    user_id=user_id,
                    product_id=item["product_id"],
                    transaction_id=tx.transaction_id,
                    type="OUT",
                    quantity=item["quantity"],
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

            # 5. Ghi nhận nợ phải thu (RECEIVABLE)
            unpaid_amount = total_amount - amount_paid
            if unpaid_amount > 0 and customer_id:
                debt_status = "PARTIAL" if amount_paid > 0 else "UNPAID"
                self.repo.create_receivable_debt(
                    transaction_id=tx.transaction_id,
                    user_id=user_id,
                    customer_id=customer_id,
                    amount=unpaid_amount,
                    status=debt_status,
                )

            self.db.commit()
            self.db.refresh(tx)

            return {
                "status": "success",
                "success": True,
                "message": "Bán hàng thành công",
                "transaction_id": tx.transaction_id,
                "total_amount": float(total_amount),
                "quantity": float(sum([item["quantity"] for item in processed_items])),
                "amount_paid": float(amount_paid),
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
                product_id = self.repo.get_product_id_by_name(
                    user_id=user_id,
                    name=product_name
                )

            if not product_id:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm '{product_name}'."
                }

            stock = self.repo.get_latest_stock(
                user_id=user_id,
                product_id=product_id
            )

            product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=product_id)
            
            unit_price = 0.0
            default_unit = ""
            if product_obj:
                if hasattr(product_obj, "unit_price") and product_obj.unit_price is not None:
                    unit_price = float(product_obj.unit_price)
                elif hasattr(product_obj, "price") and product_obj.price is not None:
                    unit_price = float(product_obj.price)

                if hasattr(product_obj, "default_unit") and product_obj.default_unit is not None:
                    default_unit = str(product_obj.default_unit)
                elif hasattr(product_obj, "unit") and product_obj.unit is not None:
                    default_unit = str(product_obj.unit)
            
            actual_product_name = product_name or (getattr(product_obj, "name", "") if product_obj else "")

            return {
                "status": "success",
                "success": True,
                "message": f"Sản phẩm '{actual_product_name}' còn {stock}.",
                "product_id": product_id,
                "product_name": actual_product_name,
                "quantity": float(stock),
                "unit_price": unit_price,
                "default_unit": default_unit
            }

        except Exception as e:
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi kiểm tra tồn kho: {str(e)}"
            }

    # Alias phương thức
    process_export = sell_goods
    process_import = import_goods
    process_check_stock = check_stock