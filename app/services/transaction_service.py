from math import ceil
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

# IMPORT CÁC MODELS
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.intent_model import Intent
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt

from app.models.intent_model import Intent
from datetime import datetime, timedelta
import unicodedata

# IMPORT REPOSITORIES
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.product_repository import (
    get_product_by_name,
    create_product
)
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session

class TransactionService:

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
                Intent.name_intent == groq_intent
            )
            .first()
        )

        if not db_intent:
            raise ValueError(
                f"Intent '{groq_intent}' không tồn tại trong database"
            )

        intent_id = db_intent.intent_id

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

                transaction_date = (
                    datetime.now() - timedelta(days=1)
                )

            elif "hôm kia" in date_text:

                transaction_date = (
                    datetime.now() - timedelta(days=2)
                )

            elif "ngày mai" in date_text:

                transaction_date = (
                    datetime.now() + timedelta(days=1)
                )

            else:

                try:

                    transaction_date = datetime.fromisoformat(
                        date_text[:10]
                    )

                except Exception:
                    pass

        # ==========================================================
        # 4. XÁC ĐỊNH LOẠI INTENT
        # ==========================================================

        SALES_INTENTS = {
            "ban_hang"
        }

        PURCHASE_INTENTS = {
            "nhap_hang"
        }

        MONEY_IN_INTENTS = {
            "thu_tien",
            "thu_no_phai_thu",
            "thu_no_khach_hang"
        }

        MONEY_OUT_INTENTS = {
            "chi_tien",
            "hang_hong",
            "hoan_tien"
        }

        MONEY_OUT_DEBT_INTENTS ={
            "tra_no_phai_tra",
            "tra_no_nha_cung_cap"
        }

        RECEIVABLE_DEBT_INTENTS = {
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",

        }

        PAYABLE_DEBT_INTENTS = {
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"

        }
        TRANFER_INTENTS= {
            "chuyen_tien"
        }

        # ==========================================================
        # 5. VALIDATE THEO INTENT
        # ==========================================================

        if groq_intent in SALES_INTENTS:

            if not product_name:
                raise ValueError(
                    "Bán hàng phải có product"
                )

            if not quantity:
                raise ValueError(
                    "Bán hàng phải có quantity"
                )

            if not price:
                raise ValueError(
                    "Bán hàng phải có price"
                )
            if not unit:
                raise ValueError(
                    "Nhập hàng phải có unit"
                )

        elif groq_intent in PURCHASE_INTENTS:

            if not product_name:
                raise ValueError(
                    "Nhập hàng phải có product"
                )

            if not quantity:
                raise ValueError(
                    "Nhập hàng phải có quantity"
                )

            if not price:
                raise ValueError(
                    "Nhập hàng phải có price"
                )
            if not unit:
                raise ValueError(
                    "Nhập hàng phải có unit"
                )

        elif groq_intent in MONEY_IN_INTENTS:

            if not customer_name:
                raise ValueError(
                    "Thu tiền phải có khách hàng"
                )
            if not price:
                raise ValueError(
                    "Thu tiền phải có amount"
                )

        elif groq_intent in MONEY_OUT_INTENTS:

            if not price:
                raise ValueError(
                    "Chi tiền phải có amount"
                )
            
        elif groq_intent in MONEY_OUT_DEBT_INTENTS:

            if not supplier_name:
                raise ValueError(
                    "Phải có nhà cung cấp"
                )

            if not price:
                raise ValueError(
                    "Phải có giá tiền"
                )

        elif groq_intent in RECEIVABLE_DEBT_INTENTS:

            if not price:
                raise ValueError(
                    "Ghi nợ phải thu phải có amount"
                )
            

            if not customer_name:
                raise ValueError(
                    "Ghi nợ phải thu phải có customer"
                )

        elif groq_intent in PAYABLE_DEBT_INTENTS:

            if not price:
                raise ValueError(
                    "Ghi nợ phải trả phải có amount"
                )

            if not supplier_name:
                raise ValueError(
                    "Ghi nợ phải trả phải có supplier"
                )



        # ==========================================================
        # 6. TÍNH TIỀN
        # ==========================================================

        total_amount = Decimal(str(price or 0))

        

        qty = Decimal(str(quantity or 1))

        if qty <= 0:
            raise ValueError("Quantity phải lớn hơn 0")

        unit_price = (
            total_amount / qty
        )

        # ==========================================================
        # 7. XỬ LÝ ACCOUNT
        # ==========================================================

        db_account = None
        account_id = None

        # Ghi nợ → chưa thanh toán → không gắn tài khoản
        if groq_intent in [
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        ]:
            account_id = None

        else:
            # Có thanh toán → xác định tài khoản
            if payment_method:

                payment_lower = (
                    str(payment_method)
            .lower()
                    .strip()
                )

                if "tiền mặt" in payment_lower:
                    acc_type = "CASH"

                elif (
                    "chuyển khoản" in payment_lower
                    or "ngân hàng" in payment_lower
                ):
                    acc_type = "BANK"

                elif (
                    "momo" in payment_lower
                    or "ví" in payment_lower
                    or "zalopay" in payment_lower
                ):
                    acc_type = "E-WALLET"

                else:
                    acc_type = "CASH"

                db_account = (
                    db.query(Account)
                    .filter(
                        Account.user_id == user_id,
                        Account.type == acc_type
                    )
                    .first()
                )

                if not db_account:
                    db_account = Account(
                        user_id=user_id,
                        name=f"Tài khoản {acc_type}",
                        type=acc_type,
                        balance=0
                    )

                    db.add(db_account)
                    db.flush()

                account_id = db_account.account_id

        # ==========================================================
        # 8. CUSTOMER
        # ==========================================================

        customer_id = None

        if customer_name:

            db_customer = (
                db.query(Customer)
                .filter(
                    Customer.user_id == user_id,
                    Customer.name.ilike(
                        str(customer_name)
                    )
                )
                .first()
            )

            if not db_customer:

                db_customer = Customer(
                    user_id=user_id,
                    name=customer_name
                )

                db.add(db_customer)
                db.flush()

            customer_id = db_customer.customer_id

        # ==========================================================
        # 9. SUPPLIER
        # ==========================================================

        supplier_id = None

        if supplier_name:

            db_supplier = (
                db.query(Supplier)
                .filter(
                    Supplier.user_id == user_id,
                    Supplier.name.ilike(
                        str(supplier_name)
                    )
                )
                .first()
            )

            if not db_supplier:

                db_supplier = Supplier(
                    user_id=user_id,
                    name=supplier_name
                )

                db.add(db_supplier)
                db.flush()

            supplier_id = db_supplier.supplier_id

        # ==========================================================
        # 10. PAYMENT STATUS
        # ==========================================================

        payment_status = (
            "Chưa thanh toán"
            if groq_intent in ["ghi_no_phai_thu", "ghi_no_khach_hang", "ghi_no_phai_tra", "ghi_no_nha_cung_cap"]
        else "Đã thanh toán"
)

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

            input_text=analysis.get(
                "text",
                ""
            ),

            transaction_date=transaction_date
        )

        db.add(new_transaction)

        # QUAN TRỌNG:
        # lấy transaction_id trước khi tạo các bảng phụ

        db.flush()

        # ==========================================================
        # 12. PRODUCT + TRANSACTION DETAIL
        # ==========================================================

        product = None

        if product_name:

            product = get_product_by_name(
                db=db,
                user_id=user_id,
                name=product_name
            )

            if not product:

                product = create_product(
                    db=db,
                    user_id=user_id,
                    name=product_name,
                    unit=unit,
                    price=unit_price
                )

            else:

                product.unit_price = unit_price

                if unit:
                    product.default_unit = unit

                db.flush()

        # Chỉ tạo TransactionDetail nếu có product

        if product:

            detail = TransactionDetail(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                product_id=product.product_id,

                quantity=qty,

                unit=unit,

                unit_price=unit_price,

                subtotal=total_amount
            )

            db.add(detail)

            db.flush()

        # ==========================================================
        # 13. ACCOUNT BALANCE
        # ==========================================================

        if db_account:

            # BÁN HÀNG + ĐÃ THANH TOÁN
            if (
                groq_intent == "ban_hang"
            ):

                db_account.balance += total_amount

            # THU TIỀN
            elif groq_intent == "thu_tien":

                db_account.balance += total_amount

            # THU NỢ
            elif groq_intent == "thu_no_phai_thu":

                db_account.balance += total_amount
            elif groq_intent == "thu_no_khach_hang":

                db_account.balance += total_amount

            # NHẬP HÀNG + ĐÃ THANH TOÁN
            elif (
                groq_intent == "nhap_hang"
            ):

                db_account.balance -= total_amount

            # CHI TIỀN
            elif groq_intent == "chi_tien":

                db_account.balance -= total_amount

            # TRẢ NỢ
            elif groq_intent == "tra_no_phai_tra":

                db_account.balance -= total_amount

            elif groq_intent == "tra_no_nha_cung_cap":

                db_account.balance -= total_amount

            elif groq_intent == "hoan_tien":

                db_account.balance -= total_amount

            elif groq_intent == "hang_hong":

                db_account.balance -= total_amount

            elif groq_intent == "kiem_kho":

                db_account = total_amount

            elif groq_intent == "bao_cao":

                db_account = total_amount
            elif groq_intent == "chuyen_tien":

                db_account = total_amount

            

        # ==========================================================
        # 14. INVENTORY TRANSACTION
        # ==========================================================
        inventory = None
        if product:

            # -----------------------------
            # BÁN HÀNG → XUẤT KHO
            # -----------------------------
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
                else 0
            )
            print("QUANTITY BEFORE:", quantity_before)

            if groq_intent in ["ban_hang","ghi_no_phai_thu","ghi_no_khach_hang"]:

                # quantity_before = current_quantity
                quantity_after = quantity_before - qty

                if quantity_after < 0:
                    raise ValueError(
                        f"Sản phẩm '{product.name}' không đủ tồn kho"
                )

            # product.quantity = quantity_after


                inventory = InventoryTransaction(

                    user_id=user_id,
                    product_id=product.product_id,
                    transaction_id=(
                        new_transaction.transaction_id
                    ),
                    type="OUT",
                    quantity=qty,
                    unit=unit,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    note="Xuất kho do bán hàng"
                )

                db.add(inventory)

            # -----------------------------
            # NHẬP HÀNG → NHẬP KHO
            # -----------------------------

            elif groq_intent in [ "nhap_hang", "ghi_no_phai_tra", "ghi_no_nha_cung_cap"]:
                # quantity_before = current_quantity
                quantity_after = quantity_before + qty
                # product.quantity = quantity_after

                inventory = InventoryTransaction(
                    user_id=user_id,

                    product_id=product.product_id,

                    transaction_id=(
                        new_transaction.transaction_id
                    ),

                    type="IN",

                    quantity=qty,

                    unit=unit,

                    quantity_before=quantity_before,

                    quantity_after=quantity_after,

                    note="Nhập kho từ giao dịch nhập hàng"
                )

                db.add(inventory)

        db.flush()

        # ==========================================================
        # 15. TẠO DEBT
        # ==========================================================

        debt = None

        # -----------------------------
        # BÁN HÀNG CHƯA THANH TOÁN
        # → KHÁCH NỢ MÌNH
        # -----------------------------

        if (
            groq_intent == "ghi_no_khach_hang"
        ):

            if not customer_id:

                raise ValueError(
                    "phải có customer"
                )

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),
                user_id=user_id,
                customer_id=customer_id,
                supplier_id=None,
                direction="RECEIVABLE",
                original_amount=total_amount,
                remaining_amount=total_amount,
                status="UNPAID"
            )

            db.add(debt)

        # -----------------------------
        # NHẬP HÀNG CHƯA THANH TOÁN
        # → MÌNH NỢ NHÀ CUNG CẤP
        # -----------------------------

        elif (
            groq_intent == "ghi_no_nha_cung_cap"
            
        ):

            if not supplier_id:

                raise ValueError(
                    "phải có supplier"
                )

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=None,

                supplier_id=supplier_id,

                direction="PAYABLE",

                original_amount=total_amount,

                remaining_amount=total_amount,

                status="UNPAID"
            )

            db.add(debt)

        # -----------------------------
        # GHI NỢ PHẢI THU
        # -----------------------------

        elif groq_intent == "ghi_no_phai_thu":

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=customer_id,

                supplier_id=None,

                direction="RECEIVABLE",

                original_amount=total_amount,

                remaining_amount=total_amount,

                status="UNPAID"
            )

            db.add(debt)

        # -----------------------------
        # GHI NỢ PHẢI TRẢ
        # -----------------------------

        elif groq_intent == "ghi_no_phai_tra":

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=None,

                supplier_id=supplier_id,

                direction="PAYABLE",

                original_amount=total_amount,

                remaining_amount=total_amount,

                status="UNPAID"
            )

            db.add(debt)

        db.flush()

        # ==========================================================
        # 16. COMMIT TOÀN BỘ
        # ==========================================================

        db.commit()

        db.refresh(new_transaction)

        # ==========================================================
        # 17. RETURN
        # ==========================================================

        return {

            "transaction_id": (
                new_transaction.transaction_id
            ),
            "user_id": user_id,

            "intent_id": intent_id,

            "account_id": account_id,

            "customer_id": customer_id,

            "supplier_id": supplier_id,

            "product_id": (
                product.product_id
                if product
                else None
            ),

            "inventory_transaction_id":(
                inventory.inventory_transaction_id
                if inventory
                else None

            ),

            "debt_id": (
                debt.debt_id
                if debt
                else None
            ),

            "quantity": qty
                if product
                else None,

            "unit": unit
                if product
                else None,

            "unit_price": unit_price
                if product
                else None,

            "total_amount": total_amount,

            "payment_status": payment_status,

            "input_method": (
                new_transaction.input_method
            ),

            "input_text": analysis.get(
                "text",
                ""
            ),

            "transaction_date": transaction_date,

            "created_at": (
                new_transaction.created_at.isoformat()
                if new_transaction.created_at
                else None
            ),

            "updated_at": (
                new_transaction.updated_at.isoformat()
                if new_transaction.updated_at
                else None
            )
        }

    # list 
    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 20
    ):

        transactions, total = (
            TransactionRepository.get_transactions(
                db=db,
                user_id=user_id,
                page=page,
                limit=limit
            )
        )

        total_pages = ceil(total / limit)

        data = []

        for transaction in transactions:

            details = []

            for detail in transaction.transaction_detail:

                details.append({
                    "detail_id": detail.detail_id,
                    "quantity": float(detail.quantity),
                    "unit": detail.unit,
                    "unit_price": float(detail.unit_price),
                    "subtotal": float(detail.subtotal),
                    "product_id": detail.product_id,
                    "product": (
                        {
                            "name": detail.product.name,
                            "image": detail.product.img 
                        }
                        if detail.product
                        else None
                    )
                })

            data.append({
                "transaction_id": transaction.transaction_id,
                "intent": (
                    transaction.intent.name_intent
                    if transaction.intent
                    else None
                ),
                "account": (
                    {
                        
                        "name": transaction.account.name,
                        "type": transaction.account.type,
                    }
                    if transaction.account
                    else None
                ),

                "customer": (
                    {
                        
                        "name": transaction.customer.name,
                    }
                    if transaction.customer
                    else None
                ),

                "supplier": (
                    {
                        
                        "name": transaction.supplier.name,
                    }
                    if transaction.supplier
                    else None
                ),

                "total_amount": float(
                    transaction.total_amount
                ),

                "payment_status": transaction.payment_status,

                "input_method": transaction.input_method,

                "input_text": transaction.input_text,

                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
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



    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):

        transaction = (
            TransactionRepository.get_transaction_by_id(
                db=db,
                user_id=user_id,
                transaction_id=transaction_id
            )
        )

        if not transaction:
            raise ValueError(
            "Không tìm thấy giao dịch"
            )

        details = []

        for detail in transaction.transaction_detail:

            details.append({
                "detail_id": detail.detail_id,
                "product_id": detail.product_id,
                "quantity": float(detail.quantity),
                "unit": detail.unit,
                "unit_price": float(detail.unit_price),
                "subtotal": float(detail.subtotal),

                "product": (
                    {
                        "name": detail.product.name,
                        "image": detail.product.img
                    }
                    if detail.product
                    else None
                )
            })

        return {
            "transaction_id": transaction.transaction_id,

            "intent": (
                transaction.intent.name_intent
                if transaction.intent
                else None
            ),

            "account": (
                {
                    "account_id": transaction.account.account_id,
                    "name": transaction.account.name,
                    "type": transaction.account.type
                }
                if transaction.account
                else None
            ),

            "customer": (
                {
    
                    "name": transaction.customer.name
                }
                if transaction.customer
                else None
            ),

            "supplier": (
                {
        
                    "name": transaction.supplier.name
                }
                if transaction.supplier
                else None
            ),

            "total_amount": float(
                transaction.total_amount
            ),

            "payment_status": transaction.payment_status,

            "input_method": transaction.input_method,

            "input_text": transaction.input_text,

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



    @staticmethod
    def update_transaction(
        db: Session,
        user_id: int,
        transaction_id: int,
        data: dict
    ):
        try:

            # ==========================================================
            # 1. LẤY TRANSACTION CŨ
            # ==========================================================

            transaction = (
                db.query(Transaction)
                .filter(
                    Transaction.transaction_id == transaction_id,
                    Transaction.user_id == user_id
                )
                .first()
            )

            if not transaction:
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy giao dịch"
                )

            # ==========================================================
            # 2. LƯU THÔNG TIN CŨ
            # ==========================================================

            old_intent = (
                transaction.intent.name_intent
                if transaction.intent
                else None
            )

            old_amount = Decimal(
                str(transaction.total_amount or 0)
            )

            old_account_id = transaction.account_id
            old_payment_status = transaction.payment_status

            old_customer_id = transaction.customer_id
            old_supplier_id = transaction.supplier_id

            # ==========================================================
            # 3. LẤY INVENTORY CŨ
            # ==========================================================

            old_inventory = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.transaction_id == transaction_id,
                    InventoryTransaction.user_id == user_id
                )
                .all()
            )

            old_product_ids = set()

            for inventory in old_inventory:
                if inventory.product_id:
                    old_product_ids.add(
                        inventory.product_id
                    )

            # ==========================================================
            # 4. LẤY DETAIL CŨ
            # ==========================================================

            old_details = (
                db.query(TransactionDetail)
                .filter(
                    TransactionDetail.transaction_id == transaction_id
                )
                .all()
            )

            for detail in old_details:
                if detail.product_id:
                    old_product_ids.add(
                        detail.product_id
                    )

            # ==========================================================
            # 5. CONSTANTS
            # ==========================================================

            MONEY_IN_INTENTS = {
                "ban_hang",
                "thu_tien",
                "thu_no_phai_thu",
                "thu_no_khach_hang"
            }

            MONEY_OUT_INTENTS = {
                "nhap_hang",
                "chi_tien",
                "tra_no_phai_tra",
                "tra_no_nha_cung_cap",
                "hoan_tien",
                "hang_hong"
            }

            INVENTORY_OUT_INTENTS = {
                "ban_hang",
                "ghi_no_khach_hang",
                "ghi_no_phai_thu"
            }

            INVENTORY_IN_INTENTS = {
                "nhap_hang",
                "ghi_no_nha_cung_cap"
            }

            DEBT_INTENTS = {
                "ghi_no_khach_hang",
                "ghi_no_phai_thu",
                "ghi_no_nha_cung_cap",
                "ghi_no_phai_tra"
            }

            RECEIVABLE_DEBT_INTENTS = {
                "ghi_no_khach_hang",
                "ghi_no_phai_thu"
            }

            PAYABLE_DEBT_INTENTS = {
                "ghi_no_nha_cung_cap",
                "ghi_no_phai_tra"
            }
            CUSTOMER_INTENTS = {
                "ban_hang",
                "thu_tien",
                "thu_no_phai_thu",
                "thu_no_khach_hang",
                "ghi_no_khach_hang",
            }
            
            SUPPLIER_INTENTS = {
                "nhap_hang",
                "tra_no_phai_tra",
                "tra_no_nha_cung_cap",
                "ghi_no_nha_cung_cap",
                "ghi_no_phai_tra",
            }

            # ==========================================================
            # 6. NORMALIZE INTENT MỚI
            # ==========================================================

            intent_name = data.get("intent")

            if intent_name is None:
                intent_name = old_intent

            if not intent_name:
                raise HTTPException(
                    status_code=400,
                    detail="Giao dịch phải có intent"
                )

            intent_name = str(intent_name).lower().strip()

            intent_name = unicodedata.normalize(
                "NFD",
                intent_name
            )

            intent_name = "".join(
                c
                for c in intent_name
                if unicodedata.category(c) != "Mn"
            )

            intent_name = intent_name.replace(
                " ",
                "_"
            )

            # ==========================================================
            # 7. KIỂM TRA INTENT
            # ==========================================================

            new_intent = (
                db.query(Intent)
                .filter(
                    Intent.name_intent == intent_name
                )
                .first()
            )

            if not new_intent:
                raise HTTPException(
                    status_code=400,
                    detail=f"Intent '{intent_name}' không tồn tại"
                )

            transaction.intent_id = new_intent.intent_id

            # ==========================================================
            # 8. CUSTOMER
            # ==========================================================

            if intent_name in CUSTOMER_INTENTS:

                customer_name = data.get("customer")

                if customer_name is not None:

                    customer_name = str(customer_name).strip()
                    if not customer_name:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Intent '{intent_name}' "
                                "phải có khách hàng"
                            )
                        )

                    customer = (
                        db.query(Customer)
                        .filter(
                            Customer.user_id == user_id,
                            Customer.name.ilike(
                                str(customer_name)
                            )
                        )
                        .first()
                    )

                    if not customer:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Khách hàng "
                                f"'{customer_name}' "
                                "không tồn tại"
                            )
                        )
                    transaction.customer_id = (
                        customer.customer_id
                    )
                elif not transaction.customer_id:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Intent '{intent_name}' "
                            "phải có khách hàng"
                        )
                    )

            else:
                transaction.customer_id = None

            # ==========================================================
            # 9. SUPPLIER
            # ==========================================================

            if intent_name in SUPPLIER_INTENTS:

                supplier_name = data.get("supplier")

                if supplier_name is not None:

                    supplier_name = str(
                        supplier_name
                    ).strip()

                    if not supplier_name:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Intent '{intent_name}' "
                                "phải có nhà cung cấp"
                            )
                        )

                    supplier = (
                        db.query(Supplier)
                        .filter(
                            Supplier.user_id == user_id,
                            Supplier.name.ilike(
                                str(supplier_name)
                            )
                        )
                        .first()
                    )

                    if not supplier:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Nhà cung cấp "
                                f"'{supplier_name}' "
                                "không tồn tại"
                            )
                        )
                    transaction.supplier_id = (
                        supplier.supplier_id
                    )

                elif not transaction.supplier_id:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Intent '{intent_name}' "
                            "phải có nhà cung cấp"
                        )
                    )

            else:
                transaction.supplier_id = None

            # ==========================================================
            # 10. PAYMENT STATUS
            # ==========================================================

            payment_status = data.get(
                "payment_status",
                transaction.payment_status
            )

            if payment_status not in {
                "Đã thanh toán",
                "Chưa thanh toán"
            }:

                raise HTTPException(
                    status_code=400,
                    detail="Payment status không hợp lệ"
                )

            transaction.payment_status = payment_status

            # ==========================================================
            # 11. RÀNG BUỘC CUSTOMER / SUPPLIER THEO INTENT
            # ==========================================================

            if intent_name in RECEIVABLE_DEBT_INTENTS:

                if not transaction.customer_id:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Giao dịch ghi nợ phải thu "
                            "phải có khách hàng"
                        )
                    )

            if intent_name in PAYABLE_DEBT_INTENTS:

                if not transaction.supplier_id:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Giao dịch ghi nợ phải trả "
                            "phải có nhà cung cấp"
                        )
                    )

            # ==========================================================
            # 12. ACCOUNT
            # ==========================================================

            new_account_id = data.get(
                "account_id",
                transaction.account_id
            )

            # ----------------------------------------------------------
            # GHI NỢ -> KHÔNG ĐƯỢC CÓ ACCOUNT
            # ----------------------------------------------------------

            if intent_name in DEBT_INTENTS:

                if payment_status != "Chưa thanh toán":
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Intent '{intent_name}' "
                            "phải có payment_status = "
                            "'Chưa thanh toán'"
                        )
                    )

                new_account_id = None

            # ----------------------------------------------------------
            # CHƯA THANH TOÁN -> ACCOUNT = NULL
            # ----------------------------------------------------------

            elif payment_status == "Chưa thanh toán":

                new_account_id = None

            # ----------------------------------------------------------
            # ĐÃ THANH TOÁN -> ACCOUNT BẮT BUỘC
            # ----------------------------------------------------------

            elif new_account_id is None:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Giao dịch đã thanh toán "
                        "phải có account"
                    )
                )

            # ----------------------------------------------------------
            # KIỂM TRA ACCOUNT
            # ----------------------------------------------------------

            if new_account_id is not None:

                new_account = (
                    db.query(Account)
                    .filter(
                        Account.account_id == new_account_id,
                        Account.user_id == user_id
                    )
                    .first()
                )

                if not new_account:

                    raise HTTPException(
                        status_code=400,
                        detail="Account không tồn tại"
                    )

            transaction.account_id = new_account_id

            # ==========================================================
            # 13. HOÀN TÁC ACCOUNT CŨ
            # ==========================================================
            #
            # Ví dụ:
            #
            # Cũ:
            # ban_hang 500k
            # account = 1
            #
            # balance cũ = 1.000.000
            #
            # -> hoàn tác:
            # balance = 1.500.000
            #
            # Sau đó mới áp dụng transaction mới.
            # ==========================================================

            if (
                old_payment_status == "Đã thanh toán"
                and old_account_id
                and old_intent
            ):

                old_account = (
                    db.query(Account)
                    .filter(
                        Account.account_id == old_account_id,
                        Account.user_id == user_id
                    )
                    .first()
                )

                if old_account:

                    if old_intent in MONEY_IN_INTENTS:

                        old_account.balance -= old_amount

                    elif old_intent in MONEY_OUT_INTENTS:

                        old_account.balance += old_amount

            # ==========================================================
            # 14. XÓA INVENTORY CŨ
            # ==========================================================
            #
            # QUAN TRỌNG:
            #
            # Không được giữ inventory cũ khi thay đổi quantity.
            #
            # Ví dụ:
            #
            # Cũ bán 5
            # Sửa thành bán 20
            #
            # Phải bỏ OUT 5 trước,
            # sau đó tạo OUT 20.
            #
            # Nếu tồn kho không đủ -> rollback toàn bộ.
            # ==========================================================

            for inventory in old_inventory:

                db.delete(inventory)

            db.flush()

            # ==========================================================
            # 15. XÓA DETAIL CŨ
            # ==========================================================

            for detail in old_details:

                db.delete(detail)

            db.flush()

            # ==========================================================
            # 16. XÓA DEBT CŨ
            # ==========================================================

            old_debt = (
                db.query(Debt)
                .filter(
                    Debt.transaction_id == transaction_id,
                    Debt.user_id == user_id
                )
                .first()
            )

            if old_debt:

                db.delete(old_debt)
            db.flush()

            # ==========================================================
            # 16. LẤY PRODUCT DATA
            # ==========================================================

            # Hỗ trợ 2 kiểu:
            #
            # KIỂU BẠN MUỐN:
            #
            # {
            #   "product": "Sữa tươi",
            #   "quantity": 1,
            #   "unit": "thùng",
            #   "unit_price": 100000
            # }
            #
            # Hoặc:
            #
            # {
            #   "details": [...]
            # }

            details_data = data.get("details")

            # ----------------------------------------------------------
            # Nếu không có details
            # => chuyển body phẳng thành 1 detail
            # ----------------------------------------------------------

            if details_data is None:

                has_product_data = any(
                    key in data
                    for key in [
                        "product",
                        "quantity",
                        "unit",
                        "unit_price"
                    ]
                )

                if has_product_data:

                    details_data = [
                        {
                            "product": data.get("product"),
                            "quantity": data.get("quantity"),
                            "unit": data.get("unit"),
                            "unit_price": data.get(
                                "unit_price"
                            )
                        }
                    ]

                else:

                    details_data = []

            # ==========================================================
            # 17. INTENT CẦN PRODUCT
            # ==========================================================

            needs_inventory = (
                intent_name in INVENTORY_OUT_INTENTS
                or intent_name in INVENTORY_IN_INTENTS
            )

            if needs_inventory and not details_data:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Intent '{intent_name}' "
                        "phải có ít nhất một sản phẩm"
                    )
                )

            # ==========================================================
            # 18. TẠO DETAIL MỚI
            # ==========================================================

            new_product_ids = set()

            total_amount = Decimal("0")

            for item in details_data:

                # ------------------------------------------------------
                # PRODUCT NAME
                # ------------------------------------------------------

                product_name = item.get("product")

                if not product_name:

                    raise HTTPException(
                        status_code=400,
                        detail="Không có tên sản phẩm"
                    )

                product_name = str(
                    product_name
                ).strip()

                # ------------------------------------------------------
                # QUANTITY
                # ------------------------------------------------------

                try:

                    quantity = Decimal(
                        str(
                            item.get(
                                "quantity",
                                0
                            )
                        )
                    )

                except Exception:

                    raise HTTPException(
                        status_code=400,
                        detail="Quantity không hợp lệ"
                    )

                if quantity <= 0:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Quantity phải lớn hơn 0"
                        )
                    )

                # ------------------------------------------------------
                # UNIT
                # ------------------------------------------------------

                unit = item.get("unit")

                if not unit:

                    raise HTTPException(
                        status_code=400,
                        detail="Product phải có unit"
                    )

                # ------------------------------------------------------
                # UNIT PRICE
                # ------------------------------------------------------

                try:

                    unit_price = Decimal(
                        str(
                            item.get(
                                "unit_price",
                                0
                            )
                        )
                    )

                except Exception:

                    raise HTTPException(
                        status_code=400,
                        detail="Unit price không hợp lệ"
                    )

                if unit_price < 0:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Unit price không được âm"
                        )
                    )

                # ------------------------------------------------------
                # TÌM PRODUCT
                # ------------------------------------------------------

                product_obj = get_product_by_name(
                    db=db,
                    user_id=user_id,
                    name=product_name
                )

                # ======================================================
                # QUAN TRỌNG:
                #
                # KHÔNG ĐƯỢC CREATE PRODUCT
                # ======================================================

                if not product_obj:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Sản phẩm '{product_name}' "
                            "không tồn tại trong bảng Product"
                        )
                    )

                # ------------------------------------------------------
                #  LƯU PRODUCT ID
                # ------------------------------------------------------

                new_product_ids.add(
                    product_obj.product_id
                )

                # ------------------------------------------------------
                # SUBTOTAL
                # ------------------------------------------------------

                subtotal = (
                    quantity * unit_price
                )

                total_amount += subtotal

                # ------------------------------------------------------
                # DETAIL
                # ------------------------------------------------------

                new_detail = TransactionDetail(
                    transaction_id=transaction_id,
                    product_id=product_obj.product_id,
                    quantity=quantity,
                    unit=unit,
                    unit_price=unit_price,
                    subtotal=subtotal
                )

                db.add(new_detail)

            db.flush()

            # ==========================================================
            # 19. UPDATE TOTAL
            # ==========================================================

            # Nếu có product detail
            if details_data:

                transaction.total_amount = (
                    total_amount
                )

            # Nếu không có detail
            elif "total_amount" in data:

                try:

                    transaction.total_amount = Decimal(
                        str(
                            data["total_amount"]
                        )
                    )

                except Exception:

                    raise HTTPException(
                        status_code=400,
                        detail="Total amount không hợp lệ"
                    )

            # Nếu không truyền total và không có detail
            # giữ amount cũ

            new_amount = Decimal(
                str(
                    transaction.total_amount or 0
                )
            )

            if new_amount < 0:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Total amount không được âm"
                    )
                )

            # ==========================================================
            # 20. INPUT TEXT
            # ==========================================================

            if "input_text" in data:

                transaction.input_text = (
                    data["input_text"]
                )

            # ==========================================================
            # 21. TRANSACTION DATE
            # ==========================================================

            if "transaction_date" in data:

                transaction.transaction_date = (
                    data["transaction_date"]
                )

            db.flush()

            # ==========================================================
            # 22. TẠO INVENTORY MỚI
            # ==========================================================

            inventory_type = None

            if intent_name in INVENTORY_OUT_INTENTS:

                inventory_type = "OUT"

            elif intent_name in INVENTORY_IN_INTENTS:

                inventory_type = "IN"

            if inventory_type:

                transaction_details = (
                    db.query(TransactionDetail)
                    .filter(
                        TransactionDetail.transaction_id
                        == transaction_id
                    )
                    .all()
                )

                for detail in transaction_details:

                    inventory = InventoryTransaction(
                        user_id=user_id,
                        product_id=detail.product_id,
                        transaction_id=transaction_id,
                        type=inventory_type,
                        quantity=detail.quantity,
                        unit=detail.unit,
                        quantity_before=Decimal("0"),
                        quantity_after=Decimal("0"),
                        note=(
                            "Cập nhật tồn kho "
                            "từ giao dịch"
                        )
                    )

                    db.add(inventory)

            db.flush()

            # ==========================================================
            # 23. REBUILD INVENTORY
            # ==========================================================

            affected_product_ids = (
                old_product_ids |
                new_product_ids
            )

            for product_id in affected_product_ids:

                inventories = (
                    db.query(InventoryTransaction)
                    .filter(
                        InventoryTransaction.user_id
                        == user_id,
                        InventoryTransaction.product_id
                        == product_id
                    )
                    .all()
                )

                # ------------------------------------------------------
                # SORT THEO NGÀY GIAO DỊCH
                # ------------------------------------------------------

                inventory_with_date = []

                for inv in inventories:

                    tx = (
                        db.query(Transaction)
                        .filter(
                            Transaction.transaction_id
                            == inv.transaction_id
                        )
                        .first()
                    )

                    tx_date = (
                        tx.transaction_date
                        if tx and tx.transaction_date
                        else datetime.min
                    )

                    inventory_with_date.append(
                        (
                            tx_date,
                            inv.inventory_transaction_id,
                            inv
                        )
                    )

                inventory_with_date.sort(
                    key=lambda x: (
                        x[0],
                        x[1]
                    )
                )

                # ------------------------------------------------------
                # TÍNH TỒN KHO TỪ ĐẦU
                # ------------------------------------------------------

                current_quantity = Decimal("0")

                for (
                    tx_date,
                    inventory_id,
                    inventory
                ) in inventory_with_date:

                    quantity = Decimal(
                        str(
                            inventory.quantity or 0
                        )
                    )

                    inventory.quantity_before = (
                        current_quantity
                    )

                    if inventory.type == "IN":

                        current_quantity += quantity

                    elif inventory.type == "OUT":

                        current_quantity -= quantity

                    # ==================================================
                    # KHÔNG ĐƯỢC TỒN KHO ÂM
                    # ==================================================

                    if current_quantity < 0:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Sản phẩm ID "
                                f"{product_id} "
                                "không đủ tồn kho để "
                                "cập nhật giao dịch. "
                                f"Tồn kho bị âm "
                                f"({current_quantity})."
                            )
                        )

                    inventory.quantity_after = (
                        current_quantity
                    )

            db.flush()

            # ==========================================================
            # 24. TẠO DEBT MỚI
            # ==========================================================

            new_debt = None

            if intent_name in DEBT_INTENTS:

                # ------------------------------------------------------
                # RECEIVABLE
                # ------------------------------------------------------

                if intent_name in RECEIVABLE_DEBT_INTENTS:

                    if not transaction.customer_id:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Ghi nợ phải thu "
                                "phải có khách hàng"
                            )
                        )

                    new_debt = Debt(
                        transaction_id=transaction_id,
                        user_id=user_id,
                        customer_id=(
                            transaction.customer_id
                        ),
                        supplier_id=None,
                        direction="RECEIVABLE",
                        original_amount=new_amount,
                        remaining_amount=new_amount,
                        status="UNPAID"
                    )

                # ------------------------------------------------------
                # PAYABLE
                # ------------------------------------------------------

                elif intent_name in PAYABLE_DEBT_INTENTS:

                    if not transaction.supplier_id:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Ghi nợ phải trả "
                                "phải có nhà cung cấp"
                            )
                        )

                    new_debt = Debt(
                        transaction_id=transaction_id,
                        user_id=user_id,
                        customer_id=None,
                        supplier_id=(
                            transaction.supplier_id
                        ),
                        direction="PAYABLE",
                        original_amount=new_amount,
                        remaining_amount=new_amount,
                        status="UNPAID"
                    )

                if new_debt:

                    db.add(new_debt)

                    db.flush()

            # ==========================================================
            # 25. APPLY ACCOUNT MỚI
            # ==========================================================

            if (
                payment_status == "Đã thanh toán"
                and new_account_id is not None
            ):

                account = (
                    db.query(Account)
                    .filter(
                        Account.account_id
                        == new_account_id,
                        Account.user_id
                        == user_id
                    )
                    .first()
                )

                if not account:

                    raise HTTPException(
                        status_code=400,
                        detail="Account không tồn tại"
                    )

                # ------------------------------------------------------
                # TIỀN VÀO
                # ------------------------------------------------------

                if intent_name in MONEY_IN_INTENTS:

                    account.balance += new_amount

                # ------------------------------------------------------
                # TIỀN RA
                # ------------------------------------------------------

                elif intent_name in MONEY_OUT_INTENTS:

                    if (
                        Decimal(
                            str(
                                account.balance or 0
                            )
                        )
                        < new_amount
                    ):

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Tài khoản "
                                f"'{account.name}' "
                                "không đủ số dư"
                            )
                        )

                    account.balance -= new_amount

            # ==========================================================
            # 26. COMMIT
            # ==========================================================

            db.commit()

            db.refresh(transaction)

            # ==========================================================
            # 27. RETURN
            # ==========================================================

            return {

                "success": True,

                "message": (
                    "Cập nhật giao dịch thành công"
                ),

                "transaction_id": (
                    transaction.transaction_id
                ),

                "intent": intent_name,

                "intent_id": (
                    transaction.intent_id
                ),

                "account_id": (
                    transaction.account_id
                ),

                "customer_id": (
                    transaction.customer_id
                ),

                "supplier_id": (
                    transaction.supplier_id
                ),

                "total_amount": float(
                    transaction.total_amount
                ),

                "payment_status": (
                    transaction.payment_status
                ),

                "inventory_product_ids": list(
                    affected_product_ids
                ),

                "debt_id": (
                    new_debt.debt_id
                    if new_debt
                    else None
                ),

                "input_text": (
                    transaction.input_text
                ),

                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),

                "updated_at": (
                    transaction.updated_at.isoformat()
                    if transaction.updated_at
                    else None
                )
            }

        # ==============================================================
        # HTTP ERROR
        # ==============================================================

        except HTTPException:

            db.rollback()
            raise

        # ==============================================================
        # UNEXPECTED ERROR
        # ==============================================================

        except Exception as e:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail=(
                    "Cập nhật giao dịch thất bại: "
                    f"{str(e)}"
                )
            )

    @staticmethod
    def delete_transaction(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        try:
            # ==========================================================
            # 1. LẤY TRANSACTION
            # ==========================================================

            transaction = (
                db.query(Transaction)
                .filter(
                    Transaction.transaction_id == transaction_id,
                    Transaction.user_id == user_id
                )
                .first()
            )

            if not transaction:
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy giao dịch"
                )

            # ==========================================================
            # 2. KIỂM TRA ĐÃ XÓA CHƯA
            # ==========================================================

            if getattr(transaction, "is_deleted", False):
                raise HTTPException(
                    status_code=400,
                    detail="Giao dịch đã được xóa"
                )

            # ==========================================================
            # 3. LƯU THÔNG TIN CŨ
            # ==========================================================

            intent_name = (
                transaction.intent.name_intent
                if transaction.intent
                else None
            )

            amount = Decimal(
                str(transaction.total_amount or 0)
            )

            old_account_id = transaction.account_id
            payment_status = transaction.payment_status

            # ==========================================================
            # 4. CONSTANTS
            # ==========================================================

            MONEY_IN_INTENTS = {
                "ban_hang",
                "thu_tien",
                "thu_no_phai_thu",
                "thu_no_khach_hang"
            }

            MONEY_OUT_INTENTS = {
                "nhap_hang",
                "chi_tien",
                "tra_no_phai_tra",
                "tra_no_nha_cung_cap",
                "hoan_tien",
                "hang_hong"
            }

            INVENTORY_INTENTS = {
                "ban_hang",
                "ghi_no_khach_hang",
                "nhap_hang",
                "ghi_no_nha_cung_cap"
            }

            # ==========================================================
            # 5. HOÀN TÁC ACCOUNT
            # ==========================================================

            if (
                payment_status == "Đã thanh toán"
                and old_account_id
            ):

                account = (
                    db.query(Account)
                    .filter(
                        Account.account_id == old_account_id,
                        Account.user_id == user_id
                    )
                    .first()
                )

                if account:

                    # Giao dịch tiền vào
                    # -> xóa giao dịch thì phải trừ tiền ra
                    if intent_name in MONEY_IN_INTENTS:

                        account.balance -= amount

                    # Giao dịch tiền ra
                    # -> xóa giao dịch thì trả tiền lại
                    elif intent_name in MONEY_OUT_INTENTS:

                        account.balance += amount

            # ==========================================================
            # 6. LẤY INVENTORY CỦA TRANSACTION
            # ==========================================================

            inventories = (
                db.query(InventoryTransaction)
                .filter(
                    InventoryTransaction.transaction_id == transaction_id,
                    InventoryTransaction.user_id == user_id
                )
                .all()
            )

            affected_product_ids = set()

            for inventory in inventories:

                if inventory.product_id:
                    affected_product_ids.add(
                        inventory.product_id
                    )

            # ==========================================================
            # 7. XÓA INVENTORY CỦA TRANSACTION
            # ==========================================================

            for inventory in inventories:
                db.delete(inventory)

            db.flush()

            # ==========================================================
            # 8. LẤY DETAILS
            # ==========================================================

            details = (
                db.query(TransactionDetail)
                .filter(
                    TransactionDetail.transaction_id == transaction_id
                )
                .all()
            )

            for detail in details:

                if detail.product_id:
                    affected_product_ids.add(
                        detail.product_id
                    )

            # ==========================================================
            # 9. XÓA DEBT
            # ==========================================================

            debt = (
                db.query(Debt)
                .filter(
                    Debt.transaction_id == transaction_id,
                    Debt.user_id == user_id
                )
                .first()
            )

            if debt:
                db.delete(debt)

            db.flush()

            # ==========================================================
            # 10. XÓA MỀM TRANSACTION
            # ==========================================================

            transaction.is_deleted = True
            transaction.deleted_at = datetime.now()

            db.flush()

            # ==========================================================
            # 11. REBUILD INVENTORY
            # ==========================================================
            #
            # Sau khi xóa inventory của transaction,
            # phải tính lại tồn kho của các product bị ảnh hưởng.
            #
            # ==========================================================

            for product_id in affected_product_ids:

                inventories = (
                    db.query(InventoryTransaction)
                    .filter(
                        InventoryTransaction.user_id == user_id,
                        InventoryTransaction.product_id == product_id
                    )
                    .all()
                )

                # ------------------------------------------------------
                # SẮP XẾP THEO NGÀY TRANSACTION
                # ------------------------------------------------------

                def inventory_sort_key(inv):

                    tx = (
                        db.query(Transaction)
                        .filter(
                            Transaction.transaction_id
                            == inv.transaction_id
                        )
                        .first()
                    )

                    if tx and tx.transaction_date:
                        return (
                            tx.transaction_date,
                            inv.inventory_transaction_id
                        )

                    return (
                        inv.inventory_transaction_id,
                    )

                inventories.sort(
                    key=inventory_sort_key
                )

                current_quantity = Decimal("0")

                # ------------------------------------------------------
                # TÍNH LẠI
                # ------------------------------------------------------

                for inventory in inventories:

                    quantity = Decimal(
                        str(inventory.quantity or 0)
                    )

                    inventory.quantity_before = (
                        current_quantity
                    )

                    if inventory.type == "IN":

                        current_quantity += quantity

                    elif inventory.type == "OUT":

                        current_quantity -= quantity

                    # Không cho tồn kho âm
                    if current_quantity < 0:

                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Sản phẩm ID {product_id} "
                                f"bị âm tồn kho sau khi xóa "
                                f"({current_quantity})"
                            )
                        )

                    inventory.quantity_after = (
                        current_quantity
                    )

            db.flush()

            # ==========================================================
            # 12. COMMIT
            # ==========================================================

            db.commit()

            # ==========================================================
            # 13. RETURN
            # ==========================================================

            return {
                "success": True,
                "message": "Xóa giao dịch thành công",
                "transaction_id": transaction_id,
                "intent": intent_name,
                "deleted": True,
                "deleted_at": (
                    transaction.deleted_at.isoformat()
                    if transaction.deleted_at
                    else None
                ),
                "inventory_product_ids": list(
                    affected_product_ids
                )
            }

        # ==============================================================
        # HTTP ERROR
        # ==============================================================

        except HTTPException:

            db.rollback()
            raise

        # ==============================================================
        # UNEXPECTED ERROR
        # ==============================================================

        except Exception as e:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail=f"Xóa giao dịch thất bại: {str(e)}"
            )
    