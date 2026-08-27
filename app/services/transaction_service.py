from math import ceil
from datetime import datetime, timedelta
from decimal import Decimal
import unicodedata

from fastapi import HTTPException
from sqlalchemy.orm import Session

# ==========================================================
# IMPORT MODELS
# ==========================================================

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.intent_model import Intent
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt

# ==========================================================
# IMPORT REPOSITORIES
# ==========================================================

from app.repositories.transaction_repository import TransactionRepository
from app.repositories.product_repository import (
    get_product_by_name,
    create_product
)


class TransactionService:

    # ==========================================================
    # SAVE GROQ TRANSACTION
    # ==========================================================

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
                c
                for c in text
                if unicodedata.category(c) != "Mn"
            )

        analysis = groq_result.get(
            "transaction_analysis",
            {}
        )

        entities = analysis.get(
            "entities",
            {}
        )

        groq_intent = (
            analysis.get(
                "intent",
                ""
            )
            .lower()
            .strip()
        )

        if not groq_intent:
            raise ValueError(
                "Không xác định được intent"
            )

        # Chuyển intent tiếng Việt về dạng không dấu
        # Ví dụ:
        # "bán hàng" -> "ban_hang"
        # "nhập hàng" -> "nhap_hang"

        groq_intent = remove_accents(
            groq_intent
        )

        groq_intent = groq_intent.replace(
            " ",
            "_"
        )

        # ==========================================================
        # TÌM INTENT TRONG DATABASE
        # ==========================================================

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

        customer_name = entities.get(
            "customer"
        )

        supplier_name = entities.get(
            "supplier"
        )

        nlp_date = entities.get(
            "date"
        )

        # ==========================================================
        # 3. XỬ LÝ NGÀY
        # ==========================================================

        transaction_date = datetime.now()

        if nlp_date:

            date_text = (
                str(nlp_date)
                .lower()
                .strip()
            )

            if "hôm qua" in date_text:

                transaction_date = (
                    datetime.now()
                    - timedelta(days=1)
                )

            elif "hôm kia" in date_text:

                transaction_date = (
                    datetime.now()
                    - timedelta(days=2)
                )

            elif "ngày mai" in date_text:

                transaction_date = (
                    datetime.now()
                    + timedelta(days=1)
                )

            else:

                try:

                    transaction_date = (
                        datetime.fromisoformat(
                            date_text[:10]
                        )
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

        MONEY_OUT_DEBT_INTENTS = {
            "tra_no_phai_tra",
            "tra_no_nha_cung_cap"
        }

        RECEIVABLE_DEBT_INTENTS = {
            "ghi_no_phai_thu",
            "ghi_no_khach_hang"
        }

        PAYABLE_DEBT_INTENTS = {
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        }

        TRANSFER_INTENTS = {
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
                    "Bán hàng phải có unit"
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

        total_amount = Decimal(
            str(price or 0)
        )

        qty = Decimal(
            str(quantity or 1)
        )

        if qty <= 0:
            raise ValueError(
                "Quantity phải lớn hơn 0"
            )

        unit_price = (
            total_amount / qty
        )

        # ==========================================================
        # 7. XỬ LÝ ACCOUNT
        # ==========================================================

        db_account = None

        account_id = None

        # ==========================================================
        # GHI NỢ
        # Chưa thanh toán -> không gắn tài khoản
        # ==========================================================

        if groq_intent in [
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        ]:

            account_id = None

        else:

            # ======================================================
            # CÓ THANH TOÁN -> XÁC ĐỊNH TÀI KHOẢN
            # ======================================================

            if payment_method:

                payment_lower = (
                    str(payment_method)
                    .lower()
                    .strip()
                )

                # Tiền mặt
                if "tiền mặt" in payment_lower:

                    acc_type = "CASH"

                # Chuyển khoản / ngân hàng
                elif (
                    "chuyển khoản" in payment_lower
                    or "ngân hàng" in payment_lower
                ):

                    acc_type = "BANK"

                # Ví điện tử
                elif (
                    "momo" in payment_lower
                    or "ví" in payment_lower
                    or "zalopay" in payment_lower
                ):

                    acc_type = "E-WALLET"

                else:

                    acc_type = "CASH"

                # ==================================================
                # TÌM ACCOUNT
                # ==================================================

                db_account = (
                    db.query(Account)
                    .filter(
                        Account.user_id == user_id,
                        Account.type == acc_type
                    )
                    .first()
                )

                # ==================================================
                # NẾU CHƯA CÓ -> TẠO ACCOUNT
                # ==================================================

                if not db_account:

                    db_account = Account(
                        user_id=user_id,
                        name=f"Tài khoản {acc_type}",
                        type=acc_type,
                        balance=0
                    )

                    db.add(
                        db_account
                    )

                    db.flush()

                account_id = (
                    db_account.account_id
                )

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

                db.add(
                    db_customer
                )

                db.flush()

            customer_id = (
                db_customer.customer_id
            )

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

                db.add(
                    db_supplier
                )

                db.flush()

            supplier_id = (
                db_supplier.supplier_id
            )

        # ==========================================================
        # 10. PAYMENT STATUS
        # ==========================================================

        unpaid_intents = [
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        ]

        payment_status = (
            "Chưa thanh toán"
            if groq_intent in unpaid_intents
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

        db.add(
            new_transaction
        )

        # ==========================================================
        # QUAN TRỌNG
        # Lấy transaction_id trước khi tạo bảng phụ
        # ==========================================================

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

            # ======================================================
            # PRODUCT CHƯA TỒN TẠI
            # ======================================================

            if not product:

                product = create_product(
                    db=db,
                    user_id=user_id,
                    name=product_name,
                    unit=unit,
                    price=unit_price
                )

            # ======================================================
            # PRODUCT ĐÃ TỒN TẠI
            # ======================================================

            else:

                product.unit_price = (
                    unit_price
                )

                if unit:

                    product.default_unit = (
                        unit
                    )

                db.flush()

        # ==========================================================
        # CHỈ TẠO TRANSACTION DETAIL NẾU CÓ PRODUCT
        # ==========================================================

        if product:

            detail = TransactionDetail(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                product_id=(
                    product.product_id
                ),

                quantity=qty,

                unit=unit,

                unit_price=unit_price,

                subtotal=total_amount
            )

            db.add(
                detail
            )

            db.flush()

        # ==========================================================
        # 13. ACCOUNT BALANCE
        # ==========================================================

        if db_account:

            # ======================================================
            # BÁN HÀNG + ĐÃ THANH TOÁN
            # ======================================================

            if groq_intent == "ban_hang":

                db_account.balance += (
                    total_amount
                )

            # ======================================================
            # THU TIỀN
            # ======================================================

            elif groq_intent == "thu_tien":

                db_account.balance += (
                    total_amount
                )

            # ======================================================
            # THU NỢ
            # ======================================================

            elif groq_intent == "thu_no_phai_thu":

                db_account.balance += (
                    total_amount
                )

            elif groq_intent == "thu_no_khach_hang":

                db_account.balance += (
                    total_amount
                )

            # ======================================================
            # NHẬP HÀNG + ĐÃ THANH TOÁN
            # ======================================================

            elif groq_intent == "nhap_hang":

                db_account.balance -= (
                    total_amount
                )

            # ======================================================
            # CHI TIỀN
            # ======================================================

            elif groq_intent == "chi_tien":

                db_account.balance -= (
                    total_amount
                )

            # ======================================================
            # TRẢ NỢ
            # ======================================================

            elif groq_intent == "tra_no_phai_tra":

                db_account.balance -= (
                    total_amount
                )

            elif groq_intent == "tra_no_nha_cung_cap":

                db_account.balance -= (
                    total_amount
                )

            # ======================================================
            # HOÀN TIỀN
            # ======================================================

            elif groq_intent == "hoan_tien":

                db_account.balance -= (
                    total_amount
                )

            # ======================================================
            # HÀNG HỎNG
            # ======================================================

            elif groq_intent == "hang_hong":

                db_account.balance -= (
                    total_amount
                )

        # ==========================================================
        # 14. INVENTORY TRANSACTION
        # ==========================================================

        inventory = None

        if product:

            # ======================================================
            # LẤY TỒN KHO GẦN NHẤT
            # ======================================================

            last_inventory = (
                db.query(
                    InventoryTransaction
                )
                .filter(
                    InventoryTransaction.user_id == user_id,
                    InventoryTransaction.product_id
                    == product.product_id
                )
                .order_by(
                    InventoryTransaction
                    .inventory_transaction_id
                    .desc()
                )
                .first()
            )

            quantity_before = (
                last_inventory.quantity_after
                if last_inventory
                else 0
            )

            print(
                "QUANTITY BEFORE:",
                quantity_before
            )

            # ======================================================
            # BÁN HÀNG / GHI NỢ PHẢI THU
            # -> XUẤT KHO
            # ======================================================

            if groq_intent in [
                "ban_hang",
                "ghi_no_phai_thu",
                "ghi_no_khach_hang"
            ]:

                quantity_after = (
                    quantity_before - qty
                )

                if quantity_after < 0:

                    raise ValueError(
                        f"Sản phẩm '{product.name}' "
                        "không đủ tồn kho"
                    )

                inventory = InventoryTransaction(

                    user_id=user_id,

                    product_id=(
                        product.product_id
                    ),

                    transaction_id=(
                        new_transaction.transaction_id
                    ),

                    type="OUT",

                    quantity=qty,

                    unit=unit,

                    quantity_before=(
                        quantity_before
                    ),

                    quantity_after=(
                        quantity_after
                    ),

                    note="Xuất kho do bán hàng"
                )

                db.add(
                    inventory
                )

            # ======================================================
            # NHẬP HÀNG / GHI NỢ PHẢI TRẢ
            # -> NHẬP KHO
            # ======================================================

            elif groq_intent in [
                "nhap_hang",
                "ghi_no_phai_tra",
                "ghi_no_nha_cung_cap"
            ]:

                quantity_after = (
                    quantity_before + qty
                )

                inventory = InventoryTransaction(

                    user_id=user_id,

                    product_id=(
                        product.product_id
                    ),

                    transaction_id=(
                        new_transaction.transaction_id
                    ),

                    type="IN",

                    quantity=qty,

                    unit=unit,

                    quantity_before=(
                        quantity_before
                    ),

                    quantity_after=(
                        quantity_after
                    ),

                    note="Nhập kho từ giao dịch nhập hàng"
                )

                db.add(
                    inventory
                )

        db.flush()

        # ==========================================================
        # 15. TẠO DEBT
        # ==========================================================

        debt = None

        # ==========================================================
        # BÁN HÀNG CHƯA THANH TOÁN
        # -> KHÁCH NỢ MÌNH
        # ==========================================================

        if groq_intent == "ghi_no_khach_hang":

            if not customer_id:

                raise ValueError(
                    "Phải có customer"
                )

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=customer_id,

                supplier_id=None,

                direction="RECEIVABLE",

                original_amount=(
                    total_amount
                ),

                remaining_amount=(
                    total_amount
                ),

                status="UNPAID"
            )

            db.add(
                debt
            )

        # ==========================================================
        # NHẬP HÀNG CHƯA THANH TOÁN
        # -> MÌNH NỢ NHÀ CUNG CẤP
        # ==========================================================

        elif groq_intent == "ghi_no_nha_cung_cap":

            if not supplier_id:

                raise ValueError(
                    "Phải có supplier"
                )

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=None,

                supplier_id=supplier_id,

                direction="PAYABLE",

                original_amount=(
                    total_amount
                ),

                remaining_amount=(
                    total_amount
                ),

                status="UNPAID"
            )

            db.add(
                debt
            )

        # ==========================================================
        # GHI NỢ PHẢI THU
        # ==========================================================

        elif groq_intent == "ghi_no_phai_thu":

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=customer_id,

                supplier_id=None,

                direction="RECEIVABLE",

                original_amount=(
                    total_amount
                ),

                remaining_amount=(
                    total_amount
                ),

                status="UNPAID"
            )

            db.add(
                debt
            )

        # ==========================================================
        # GHI NỢ PHẢI TRẢ
        # ==========================================================

        elif groq_intent == "ghi_no_phai_tra":

            debt = Debt(

                transaction_id=(
                    new_transaction.transaction_id
                ),

                user_id=user_id,

                customer_id=None,

                supplier_id=supplier_id,

                direction="PAYABLE",

                original_amount=(
                    total_amount
                ),

                remaining_amount=(
                    total_amount
                ),

                status="UNPAID"
            )

            db.add(
                debt
            )

        db.flush()

        # ==========================================================
        # 16. COMMIT TOÀN BỘ
        # ==========================================================

        db.commit()

        db.refresh(
            new_transaction
        )

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

            "inventory_transaction_id": (
                inventory.inventory_transaction_id
                if inventory
                else None
            ),

            "debt_id": (
                debt.debt_id
                if debt
                else None
            ),

            "quantity": (
                qty
                if product
                else None
            ),

            "unit": (
                unit
                if product
                else None
            ),

            "unit_price": (
                unit_price
                if product
                else None
            ),

            "total_amount": total_amount,

            "payment_status": payment_status,

            "input_method": (
                new_transaction.input_method
            ),

            "input_text": analysis.get(
                "text",
                ""
            ),

            "transaction_date": (
                transaction_date
            ),

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

    # ==========================================================
    # GET TRANSACTIONS
    # ==========================================================

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

        total_pages = (
            ceil(total / limit)
        )

        data = []

        for transaction in transactions:

            details = []

            for detail in (
                transaction.transaction_detail
            ):

                details.append({

                    "detail_id": (
                        detail.detail_id
                    ),

                    "quantity": float(
                        detail.quantity
                    ),

                    "unit": detail.unit,

                    "unit_price": float(
                        detail.unit_price
                    ),

                    "subtotal": float(
                        detail.subtotal
                    ),

                    "product_id": (
                        detail.product_id
                    ),

                    "product": (

                        {
                            "name": (
                                detail.product.name
                            ),
                            "image": (
                                detail.product.img
                            )
                        }

                        if detail.product

                        else None
                    )
                })

            data.append({

                "transaction_id": (
                    transaction.transaction_id
                ),

                "intent": (

                    transaction.intent.name_intent

                    if transaction.intent

                    else None
                ),

                "account": (

                    {
                        "name": (
                            transaction.account.name
                        ),
                        "type": (
                            transaction.account.type
                        )
                    }

                    if transaction.account

                    else None
                ),

                "customer": (

                    {
                        "name": (
                            transaction.customer.name
                        )
                    }

                    if transaction.customer

                    else None
                ),

                "supplier": (

                    {
                        "name": (
                            transaction.supplier.name
                        )
                    }

                    if transaction.supplier

                    else None
                ),

                "total_amount": float(
                    transaction.total_amount
                ),

                "payment_status": (
                    transaction.payment_status
                ),

                "input_method": (
                    transaction.input_method
                ),

                "input_text": (
                    transaction.input_text
                ),

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

    # ==========================================================
    # GET TRANSACTION BY ID
    # ==========================================================

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

        for detail in (
            transaction.transaction_detail
        ):

            details.append({

                "detail_id": (
                    detail.detail_id
                ),

                "product_id": (
                    detail.product_id
                ),

                "quantity": float(
                    detail.quantity
                ),

                "unit": detail.unit,

                "unit_price": float(
                    detail.unit_price
                ),

                "subtotal": float(
                    detail.subtotal
                ),

                "product": (

                    {
                        "name": (
                            detail.product.name
                        ),
                        "image": (
                            detail.product.img
                        )
                    }

                    if detail.product

                    else None
                )
            })

        return {

            "transaction_id": (
                transaction.transaction_id
            ),

            "intent": (

                transaction.intent.name_intent

                if transaction.intent

                else None
            ),

            "account": (

                {
                    "account_id": (
                        transaction.account.account_id
                    ),
                    "name": (
                        transaction.account.name
                    ),
                    "type": (
                        transaction.account.type
                    )
                }

                if transaction.account

                else None
            ),

            "customer": (

                {
                    "name": (
                        transaction.customer.name
                    )
                }

                if transaction.customer

                else None
            ),

            "supplier": (

                {
                    "name": (
                        transaction.supplier.name
                    )
                }

                if transaction.supplier

                else None
            ),

            "total_amount": float(
                transaction.total_amount
            ),

            "payment_status": (
                transaction.payment_status
            ),

            "input_method": (
                transaction.input_method
            ),

            "input_text": (
                transaction.input_text
            ),

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