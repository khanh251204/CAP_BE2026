from math import ceil
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from decimal import Decimal
from datetime import datetime, timedelta
import unicodedata
from typing import Optional, Dict, Any, List

# IMPORT CÁC MODELS ĐỐI CHIẾU THEO docs/erd.md
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt

# IMPORT REPOSITORIES
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.product_repository import (
    get_product_by_name,
    create_product
)
from app.schemas.transaction_schema import TransactionCreateRequest


class TransactionService:

    @staticmethod
    def create_direct_transaction(
        db: Session,
        user_id: int,
        request: TransactionCreateRequest
    ) -> Dict[str, Any]:
        """
        Tạo Transaction trực tiếp theo đúng chuẩn Model và docs/erd.md:
        - Transaction: intent_id, category_id, account_id, customer_id, supplier_id,
                       total_amount, payment_status, input_method, input_text, note, transaction_date
        - Transaction_Detail (1-N): product_id, quantity, unit, unit_price, subtotal
        - Tự động cập nhật số dư Account nếu thanh toán thành công (PAID).
        """
        # 1. Kiểm tra intent_id nếu được truyền
        intent_id = request.intent_id
        if intent_id is not None:
            intent = db.query(Intent).filter(Intent.intent_id == intent_id).first()
            if not intent:
                raise ValueError(f"Không tìm thấy Intent với id {intent_id}")

        # 2. Kiểm tra category_id nếu được truyền
        category_id = request.category_id
        category = None
        if category_id is not None:
            category = db.query(Category).filter(
                Category.category_id == category_id,
                (Category.user_id == user_id) | (Category.user_id.is_(None))
            ).first()
            if not category:
                raise ValueError(f"Không tìm thấy Category với id {category_id}")

        # 3. Kiểm tra account_id nếu được truyền
        account_id = request.account_id
        account = None
        if account_id is not None:
            account = db.query(Account).filter(
                Account.account_id == account_id,
                Account.user_id == user_id
            ).first()
            if not account:
                raise ValueError(f"Không tìm thấy Account với id {account_id}")

        # 4. Kiểm tra customer_id nếu được truyền
        customer_id = request.customer_id
        if customer_id is not None:
            customer = db.query(Customer).filter(
                Customer.customer_id == customer_id,
                Customer.user_id == user_id
            ).first()
            if not customer:
                raise ValueError(f"Không tìm thấy Customer với id {customer_id}")

        # 5. Kiểm tra supplier_id nếu được truyền
        supplier_id = request.supplier_id
        if supplier_id is not None:
            supplier = db.query(Supplier).filter(
                Supplier.supplier_id == supplier_id,
                Supplier.user_id == user_id
            ).first()
            if not supplier:
                raise ValueError(f"Không tìm thấy Supplier với id {supplier_id}")

        # 6. Tính toán total_amount
        total_amount = Decimal(str(request.total_amount or 0))
        calculated_detail_total = Decimal("0.00")

        # Chuẩn hóa payment_status theo ERD: 'PAID', 'PARTIAL', 'PENDING'
        payment_status_valid = {"PAID", "PARTIAL", "PENDING"}
        raw_payment_status = (request.payment_status or "").upper().strip()
        if raw_payment_status in payment_status_valid:
            payment_status = raw_payment_status
        else:
            payment_status = "PAID" if account_id is not None else "PENDING"

        # Chuẩn hóa input_method theo ERD: 'VOICE', 'MANUAL'
        raw_input_method = (request.input_method or "MANUAL").upper().strip()
        input_method = raw_input_method if raw_input_method in {"VOICE", "MANUAL"} else "MANUAL"

        transaction_date = request.transaction_date or datetime.now()

        # 7. Khởi tạo Transaction
        new_transaction = Transaction(
            user_id=user_id,
            intent_id=intent_id,
            category_id=category_id,
            account_id=account_id,
            customer_id=customer_id,
            supplier_id=supplier_id,
            total_amount=total_amount,
            payment_status=payment_status,
            input_method=input_method,
            input_text=request.input_text or request.text or "",
            note=request.note,
            transaction_date=transaction_date,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(new_transaction)
        db.flush()

        # 8. Xử lý danh sách chi tiết (Transaction_Detail) nếu có
        saved_details = []
        if request.details:
            for item in request.details:
                prod = db.query(Product).filter(
                    Product.product_id == item.product_id,
                    Product.user_id == user_id
                ).first()
                if not prod:
                    raise ValueError(f"Không tìm thấy sản phẩm với id {item.product_id}")

                qty = Decimal(str(item.quantity))
                u_price = Decimal(str(item.unit_price))
                subtotal = Decimal(str(item.subtotal)) if item.subtotal is not None else (qty * u_price)
                calculated_detail_total += subtotal

                detail = TransactionDetail(
                    transaction_id=new_transaction.transaction_id,
                    product_id=prod.product_id,
                    quantity=qty,
                    unit=item.unit or prod.default_unit or "cái",
                    unit_price=u_price,
                    subtotal=subtotal
                )
                db.add(detail)
                saved_details.append(detail)

            db.flush()

            # Nếu total_amount ban đầu bằng 0 thì cập nhật theo tổng details
            if total_amount == 0 and calculated_detail_total > 0:
                total_amount = calculated_detail_total
                new_transaction.total_amount = total_amount

        # 9. Cập nhật số dư tài khoản nếu đã thanh toán (PAID) và có account
        if account and payment_status == "PAID":
            if category:
                if category.category_type == "INCOME":
                    account.balance += total_amount
                elif category.category_type == "EXPENSE":
                    account.balance -= total_amount
            account.updated_at = datetime.now()

        db.commit()
        db.refresh(new_transaction)

        return {
            "transaction_id": new_transaction.transaction_id,
            "user_id": new_transaction.user_id,
            "intent_id": new_transaction.intent_id,
            "category_id": new_transaction.category_id,
            "account_id": new_transaction.account_id,
            "customer_id": new_transaction.customer_id,
            "supplier_id": new_transaction.supplier_id,
            "total_amount": float(new_transaction.total_amount),
            "payment_status": new_transaction.payment_status,
            "input_method": new_transaction.input_method,
            "input_text": new_transaction.input_text,
            "note": new_transaction.note,
            "transaction_date": new_transaction.transaction_date.isoformat() if new_transaction.transaction_date else None,
            "created_at": new_transaction.created_at.isoformat() if new_transaction.created_at else None,
            "updated_at": new_transaction.updated_at.isoformat() if new_transaction.updated_at else None,
            "details_count": len(saved_details)
        }

    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict
    ):
        # ==========================================================
        # 1. LẤY KẾT QUẢ GROQ
        # ==========================================================
        def remove_accents(text: str) -> str:
            text = unicodedata.normalize("NFD", text)
            return "".join(
                c for c in text
                if unicodedata.category(c) != "Mn"
            )

        analysis = groq_result.get("transaction_analysis", {})
        entities = analysis.get("entities", {})

        groq_intent = (
            analysis.get("intent", "")
            .lower()
            .strip()
        )

        if not groq_intent:
            raise ValueError("Không xác định được intent")

        groq_intent = remove_accents(groq_intent)
        groq_intent = groq_intent.replace(" ", "_")

        db_intent = (
            db.query(Intent)
            .filter(
                Intent.intent_name == groq_intent
            )
            .first()
        )

        intent_id = db_intent.intent_id if db_intent else None

        # ==========================================================
        # 2. LẤY ENTITIES
        # ==========================================================
        product_name = entities.get("product")
        quantity = entities.get("quantity")
        price = entities.get("price")
        unit = entities.get("unit")

        payment_method = entities.get("payment")
        customer_name = entities.get("customer")
        supplier_name = entities.get("supplier")

        nlp_date = entities.get("date")

        # ==========================================================
        # 3. XỬ LÝ NGÀY
        # ==========================================================
        transaction_date = datetime.now()

        if nlp_date:
            date_text = str(nlp_date).lower().strip()
            if "hôm qua" in date_text:
                transaction_date = datetime.now() - timedelta(days=1)
            elif "hôm kia" in date_text:
                transaction_date = datetime.now() - timedelta(days=2)
            elif "ngày mai" in date_text:
                transaction_date = datetime.now() + timedelta(days=1)
            else:
                try:
                    transaction_date = datetime.fromisoformat(date_text[:10])
                except Exception:
                    pass

        # ==========================================================
        # 4. XÁC ĐỊNH LOẠI INTENT
        # ==========================================================
        SALES_INTENTS = {"ban_hang"}
        PURCHASE_INTENTS = {"nhap_hang", "mua_hang"}
        MONEY_IN_INTENTS = {"thu_tien", "thu_no_phai_thu", "thu_no_khach_hang"}
        MONEY_OUT_INTENTS = {"chi_tien", "hang_hong", "hoan_tien"}
        MONEY_OUT_DEBT_INTENTS = {"tra_no_phai_tra", "tra_no_nha_cung_cap"}
        RECEIVABLE_DEBT_INTENTS = {"ghi_no_phai_thu", "ghi_no_khach_hang"}
        PAYABLE_DEBT_INTENTS = {"ghi_no_phai_tra", "ghi_no_nha_cung_cap"}
        TRANSFER_INTENTS = {"chuyen_tien"}

        # ==========================================================
        # 5. VALIDATE THEO INTENT
        # ==========================================================
        if groq_intent in SALES_INTENTS:
            if not product_name:
                raise ValueError("Bán hàng phải có product")
            if not quantity:
                raise ValueError("Bán hàng phải có quantity")
            if not price:
                raise ValueError("Bán hàng phải có price")

        elif groq_intent in PURCHASE_INTENTS:
            if not product_name:
                raise ValueError("Nhập hàng phải có product")
            if not quantity:
                raise ValueError("Nhập hàng phải có quantity")
            if not price:
                raise ValueError("Nhập hàng phải có price")

        elif groq_intent in MONEY_IN_INTENTS:
            if not price:
                raise ValueError("Thu tiền phải có amount")

        elif groq_intent in MONEY_OUT_INTENTS:
            if not price:
                raise ValueError("Chi tiền phải có amount")

        elif groq_intent in MONEY_OUT_DEBT_INTENTS:
            if not supplier_name:
                raise ValueError("Phải có nhà cung cấp")
            if not price:
                raise ValueError("Phải có giá tiền")

        elif groq_intent in RECEIVABLE_DEBT_INTENTS:
            if not price:
                raise ValueError("Ghi nợ phải thu phải có amount")
            if not customer_name:
                raise ValueError("Ghi nợ phải thu phải có customer")

        elif groq_intent in PAYABLE_DEBT_INTENTS:
            if not price:
                raise ValueError("Ghi nợ phải trả phải có amount")
            if not supplier_name:
                raise ValueError("Ghi nợ phải trả phải có supplier")

        # ==========================================================
        # 6. TÍNH TIỀN
        # ==========================================================
        total_amount = Decimal(str(price or 0))
        qty = Decimal(str(quantity or 1))
        if qty <= 0:
            raise ValueError("Quantity phải lớn hơn 0")

        unit_price = total_amount / qty if product_name else Decimal("0.00")

        # ==========================================================
        # 7. XỬ LÝ ACCOUNT (đúng model Account & docs/erd.md: account_type, account_name)
        # ==========================================================
        db_account = None
        account_id = None

        is_pure_debt = groq_intent in [
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        ]

        if not is_pure_debt:
            acc_type = "CASH"
            if payment_method:
                payment_lower = str(payment_method).lower().strip()
                if "tiền mặt" in payment_lower:
                    acc_type = "CASH"
                elif "chuyển khoản" in payment_lower or "ngân hàng" in payment_lower:
                    acc_type = "BANK"
                elif "momo" in payment_lower or "ví" in payment_lower or "zalopay" in payment_lower:
                    acc_type = "E-WALLET"

            db_account = (
                db.query(Account)
                .filter(
                    Account.user_id == user_id,
                    Account.account_type == acc_type
                )
                .first()
            )

            if not db_account:
                db_account = Account(
                    user_id=user_id,
                    account_name=f"Tài khoản {acc_type}",
                    account_type=acc_type,
                    balance=Decimal("0.00"),
                    currency="VND",
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(db_account)
                db.flush()

            account_id = db_account.account_id

        # ==========================================================
        # 8. CUSTOMER (đúng model Customer: customer_name, created_at, updated_at)
        # ==========================================================
        customer_id = None
        if customer_name:
            db_customer = (
                db.query(Customer)
                .filter(
                    Customer.user_id == user_id,
                    Customer.customer_name.ilike(str(customer_name))
                )
                .first()
            )

            if not db_customer:
                db_customer = Customer(
                    user_id=user_id,
                    customer_name=str(customer_name),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(db_customer)
                db.flush()

            customer_id = db_customer.customer_id

        # ==========================================================
        # 9. SUPPLIER (đúng model Supplier: supplier_name, created_at, updated_at)
        # ==========================================================
        supplier_id = None
        if supplier_name:
            db_supplier = (
                db.query(Supplier)
                .filter(
                    Supplier.user_id == user_id,
                    Supplier.supplier_name.ilike(str(supplier_name))
                )
                .first()
            )

            if not db_supplier:
                db_supplier = Supplier(
                    user_id=user_id,
                    supplier_name=str(supplier_name),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(db_supplier)
                db.flush()

            supplier_id = db_supplier.supplier_id

        # ==========================================================
        # 10. PAYMENT STATUS (Chuẩn Enum ERD: 'PAID', 'PARTIAL', 'PENDING')
        # ==========================================================
        payment_status = "PENDING" if is_pure_debt else "PAID"

        # ==========================================================
        # 11. TẠO TRANSACTION
        # ==========================================================
        new_transaction = Transaction(
            user_id=user_id,
            intent_id=intent_id,
            account_id=account_id,
            customer_id=customer_id,
            supplier_id=supplier_id,
            total_amount=total_amount,
            payment_status=payment_status,
            input_method="VOICE",
            input_text=analysis.get("text", ""),
            transaction_date=transaction_date,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(new_transaction)
        db.flush()

        # ==========================================================
        # 12. PRODUCT + TRANSACTION DETAIL (đúng model Product: product_name, default_unit)
        # ==========================================================
        product = None
        if product_name:
            product = get_product_by_name(
                db=db,
                user_id=user_id,
                product_name=product_name
            )

            if not product:
                product = create_product(
                    db=db,
                    user_id=user_id,
                    product_name=product_name,
                    unit=unit,
                    price=float(unit_price)
                )
                product.updated_at = datetime.now()
            else:
                product.unit_price = str(unit_price)
                if unit:
                    product.default_unit = unit
                product.updated_at = datetime.now()
                db.flush()

            detail = TransactionDetail(
                transaction_id=new_transaction.transaction_id,
                product_id=product.product_id,
                quantity=qty,
                unit=unit or product.default_unit or "cái",
                unit_price=unit_price,
                subtotal=total_amount
            )
            db.add(detail)
            db.flush()

        # ==========================================================
        # 13. ACCOUNT BALANCE (cập nhật số dư đúng nghiệp vụ)
        # ==========================================================
        if db_account:
            if groq_intent in ("ban_hang", "thu_tien", "thu_no_phai_thu", "thu_no_khach_hang"):
                db_account.balance += total_amount
            elif groq_intent in ("nhap_hang", "mua_hang", "chi_tien", "tra_no_phai_tra", "tra_no_nha_cung_cap", "hoan_tien", "hang_hong"):
                db_account.balance -= total_amount
            db_account.updated_at = datetime.now()

        # ==========================================================
        # 14. INVENTORY TRANSACTION (đúng model InventoryTransaction: inventory_type)
        # ==========================================================
        inventory = None
        if product:
            last_inventory = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.user_id == user_id,
                    InventoryTransaction.product_id == product.product_id
                )
                .order_by(
                    InventoryTransaction.inventory_transaction_id.desc()
                )
                .first()
            )

            quantity_before = (
                last_inventory.quantity_after
                if last_inventory
                else Decimal("0.00")
            )

            if groq_intent in ["ban_hang", "ghi_no_phai_thu", "ghi_no_khach_hang"]:
                quantity_after = quantity_before - qty
                if quantity_after < 0:
                    raise ValueError(f"Sản phẩm '{product.product_name}' không đủ tồn kho")

                inventory = InventoryTransaction(
                    user_id=user_id,
                    product_id=product.product_id,
                    transaction_id=new_transaction.transaction_id,
                    inventory_type="OUT",
                    quantity=qty,
                    unit=unit or product.default_unit,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    note="Xuất kho do bán hàng",
                    created_at=datetime.now()
                )
                db.add(inventory)

            elif groq_intent in ["nhap_hang", "mua_hang", "ghi_no_phai_tra", "ghi_no_nha_cung_cap"]:
                quantity_after = quantity_before + qty
                inventory = InventoryTransaction(
                    user_id=user_id,
                    product_id=product.product_id,
                    transaction_id=new_transaction.transaction_id,
                    inventory_type="IN",
                    quantity=qty,
                    unit=unit or product.default_unit,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    note="Nhập kho từ giao dịch nhập hàng",
                    created_at=datetime.now()
                )
                db.add(inventory)

            db.flush()

        # ==========================================================
        # 15. TẠO DEBT (đúng model Debt: remaining_debt, status theo ERD)
        # ==========================================================
        debt = None
        if groq_intent in ("ghi_no_khach_hang", "ghi_no_phai_thu"):
            if not customer_id:
                raise ValueError("Phải có thông tin khách hàng để ghi nợ")
            debt = Debt(
                transaction_id=new_transaction.transaction_id,
                user_id=user_id,
                customer_id=customer_id,
                supplier_id=None,
                direction="RECEIVABLE",
                original_amount=total_amount,
                remaining_debt=total_amount,
                status="UNPAID",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(debt)

        elif groq_intent in ("ghi_no_nha_cung_cap", "ghi_no_phai_tra"):
            if not supplier_id:
                raise ValueError("Phải có thông tin nhà cung cấp để ghi nợ")
            debt = Debt(
                transaction_id=new_transaction.transaction_id,
                user_id=user_id,
                customer_id=None,
                supplier_id=supplier_id,
                direction="PAYABLE",
                original_amount=total_amount,
                remaining_debt=total_amount,
                status="UNPAID",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(debt)

        db.flush()
        db.commit()
        db.refresh(new_transaction)

        # ==========================================================
        # 16. RETURN
        # ==========================================================
        return {
            "transaction_id": new_transaction.transaction_id,
            "user_id": user_id,
            "intent_id": intent_id,
            "account_id": account_id,
            "customer_id": customer_id,
            "supplier_id": supplier_id,
            "product_id": product.product_id if product else None,
            "inventory_transaction_id": inventory.inventory_transaction_id if inventory else None,
            "debt_id": debt.debt_id if debt else None,
            "quantity": float(qty) if product else None,
            "unit": unit or (product.default_unit if product else None),
            "unit_price": float(unit_price) if product else None,
            "total_amount": float(total_amount),
            "payment_status": new_transaction.payment_status,
            "input_method": new_transaction.input_method,
            "input_text": analysis.get("text", ""),
            "transaction_date": transaction_date.isoformat() if transaction_date else None,
            "created_at": new_transaction.created_at.isoformat() if new_transaction.created_at else None,
            "updated_at": new_transaction.updated_at.isoformat() if new_transaction.updated_at else None
        }

    # ==========================================================
    # GET LIST TRANSACTIONS (đúng tên trường theo docs/erd.md)
    # ==========================================================
    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 20
    ):
        transactions, total = TransactionRepository.get_transactions(
            db=db,
            user_id=user_id,
            page=page,
            limit=limit
        )

        total_pages = ceil(total / limit) if limit > 0 else 0
        data = []

        for transaction in transactions:
            details = []
            # Duyệt qua transaction_detail
            raw_details = transaction.transaction_detail if transaction.transaction_detail else []
            for detail in raw_details:
                prod = detail.product
                details.append({
                    "detail_id": detail.detail_id,
                    "quantity": float(detail.quantity) if detail.quantity is not None else 0.0,
                    "unit": detail.unit,
                    "unit_price": float(detail.unit_price) if detail.unit_price is not None else 0.0,
                    "subtotal": float(detail.subtotal) if detail.subtotal is not None else 0.0,
                    "product_id": detail.product_id,
                    "product": (
                        {
                            "product_id": prod.product_id,
                            "product_name": prod.product_name,
                            "name": prod.product_name,
                            "image": prod.img
                        }
                        if prod
                        else None
                    )
                })

            data.append({
                "transaction_id": transaction.transaction_id,
                "user_id": transaction.user_id,
                "intent_id": transaction.intent_id,
                "category_id": transaction.category_id,
                "account_id": transaction.account_id,
                "customer_id": transaction.customer_id,
                "supplier_id": transaction.supplier_id,
                "intent": (
                    transaction.intent.intent_name
                    if transaction.intent
                    else None
                ),
                "account": (
                    {
                        "account_id": transaction.account.account_id,
                        "account_name": transaction.account.account_name,
                        "name": transaction.account.account_name,
                        "account_type": transaction.account.account_type
                    }
                    if transaction.account
                    else None
                ),
                "customer": (
                    {
                        "customer_id": transaction.customer.customer_id,
                        "customer_name": transaction.customer.customer_name,
                        "name": transaction.customer.customer_name
                    }
                    if transaction.customer
                    else None
                ),
                "supplier": (
                    {
                        "supplier_id": transaction.supplier.supplier_id,
                        "supplier_name": transaction.supplier.supplier_name,
                        "name": transaction.supplier.supplier_name
                    }
                    if transaction.supplier
                    else None
                ),
                "total_amount": float(transaction.total_amount) if transaction.total_amount is not None else 0.0,
                "payment_status": transaction.payment_status,
                "input_method": transaction.input_method,
                "input_text": transaction.input_text,
                "note": transaction.note,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),
                "created_at": (
                    transaction.created_at.isoformat()
                    if transaction.created_at
                    else None
                ),
                "updated_at": (
                    transaction.updated_at.isoformat()
                    if transaction.updated_at
                    else None
                ),
                "details": details
            })

        return {
            "items": data,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }

    # ==========================================================
    # GET TRANSACTION BY ID (đúng tên trường theo docs/erd.md)
    # ==========================================================
    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        transaction = TransactionRepository.get_transaction_by_id(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )

        if not transaction:
            return None

        details = []
        raw_details = transaction.transaction_detail if transaction.transaction_detail else []
        for detail in raw_details:
            prod = detail.product
            details.append({
                "detail_id": detail.detail_id,
                "product_id": detail.product_id,
                "quantity": float(detail.quantity) if detail.quantity is not None else 0.0,
                "unit": detail.unit,
                "unit_price": float(detail.unit_price) if detail.unit_price is not None else 0.0,
                "subtotal": float(detail.subtotal) if detail.subtotal is not None else 0.0,
                "product": (
                    {
                        "product_id": prod.product_id,
                        "product_name": prod.product_name,
                        "name": prod.product_name,
                        "image": prod.img
                    }
                    if prod
                    else None
                )
            })

        return {
            "transaction_id": transaction.transaction_id,
            "user_id": transaction.user_id,
            "intent_id": transaction.intent_id,
            "category_id": transaction.category_id,
            "account_id": transaction.account_id,
            "customer_id": transaction.customer_id,
            "supplier_id": transaction.supplier_id,
            "intent": (
                transaction.intent.intent_name
                if transaction.intent
                else None
            ),
            "account": (
                {
                    "account_id": transaction.account.account_id,
                    "account_name": transaction.account.account_name,
                    "name": transaction.account.account_name,
                    "account_type": transaction.account.account_type
                }
                if transaction.account
                else None
            ),
            "customer": (
                {
                    "customer_id": transaction.customer.customer_id,
                    "customer_name": transaction.customer.customer_name,
                    "name": transaction.customer.customer_name
                }
                if transaction.customer
                else None
            ),
            "supplier": (
                {
                    "supplier_id": transaction.supplier.supplier_id,
                    "supplier_name": transaction.supplier.supplier_name,
                    "name": transaction.supplier.supplier_name
                }
                if transaction.supplier
                else None
            ),
            "total_amount": float(transaction.total_amount) if transaction.total_amount is not None else 0.0,
            "payment_status": transaction.payment_status,
            "input_method": transaction.input_method,
            "input_text": transaction.input_text,
            "note": transaction.note,
            "transaction_date": (
                transaction.transaction_date.isoformat()
                if transaction.transaction_date
                else None
            ),
            "created_at": (
                transaction.created_at.isoformat()
                if transaction.created_at
                else None
            ),
            "updated_at": (
                transaction.updated_at.isoformat()
                if transaction.updated_at
                else None
            ),
            "details": details
        }