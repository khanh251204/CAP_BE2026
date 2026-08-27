from math import ceil
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

# IMPORT CÃC MODELS
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
        # 1. Láº¤Y Káº¾T QUáº¢ GROQ
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
            raise ValueError("KhÃ´ng xÃ¡c Ä‘á»‹nh Ä‘Æ°á»£c intent")

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
                f"Intent '{groq_intent}' khÃ´ng tá»“n táº¡i trong database"
            )

        intent_id = db_intent.intent_id

        # ==========================================================
        # 2. Láº¤Y ENTITIES
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
        # 3. Xá»¬ LÃ NGÃ€Y
        # ==========================================================

        transaction_date = datetime.now()

        if nlp_date:

            date_text = str(nlp_date).lower().strip()

            if "hÃ´m qua" in date_text:

                transaction_date = (
                    datetime.now() - timedelta(days=1)
                )

            elif "hÃ´m kia" in date_text:

                transaction_date = (
                    datetime.now() - timedelta(days=2)
                )

            elif "ngÃ y mai" in date_text:

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
        # 4. XÃC Äá»ŠNH LOáº I INTENT
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
            "hÃ ng_há»ng",
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
                    "BÃ¡n hÃ ng pháº£i cÃ³ product"
                )

            if not quantity:
                raise ValueError(
                    "BÃ¡n hÃ ng pháº£i cÃ³ quantity"
                )

            if not price:
                raise ValueError(
                    "BÃ¡n hÃ ng pháº£i cÃ³ price"
                )
            if not unit:
                raise ValueError(
                    "Nháº­p hÃ ng pháº£i cÃ³ unit"
                )

        elif groq_intent in PURCHASE_INTENTS:

            if not product_name:
                raise ValueError(
                    "Nháº­p hÃ ng pháº£i cÃ³ product"
                )

            if not quantity:
                raise ValueError(
                    "Nháº­p hÃ ng pháº£i cÃ³ quantity"
                )

            if not price:
                raise ValueError(
                    "Nháº­p hÃ ng pháº£i cÃ³ price"
                )
            if not unit:
                raise ValueError(
                    "Nháº­p hÃ ng pháº£i cÃ³ unit"
                )

        elif groq_intent in MONEY_IN_INTENTS:

            if not customer_name:
                raise ValueError(
                    "Thu tiá»n pháº£i cÃ³ khÃ¡ch hÃ ng"
                )
            if not price:
                raise ValueError(
                    "Thu tiá»n pháº£i cÃ³ amount"
                )

        elif groq_intent in MONEY_OUT_INTENTS:

            if not price:
                raise ValueError(
                    "Chi tiá»n pháº£i cÃ³ amount"
                )

        elif groq_intent in MONEY_OUT_DEBT_INTENTS:

            if not supplier_name:
                raise ValueError(
                    "Pháº£i cÃ³ nhÃ  cung cáº¥p"
                )

            if not price:
                raise ValueError(
                    "Pháº£i cÃ³ giÃ¡ tiá»n"
                )

        elif groq_intent in RECEIVABLE_DEBT_INTENTS:

            if not price:
                raise ValueError(
                    "Ghi ná»£ pháº£i thu pháº£i cÃ³ amount"
                )


            if not customer_name:
                raise ValueError(
                    "Ghi ná»£ pháº£i thu pháº£i cÃ³ customer"
                )

        elif groq_intent in PAYABLE_DEBT_INTENTS:

            if not price:
                raise ValueError(
                    "Ghi ná»£ pháº£i tráº£ pháº£i cÃ³ amount"
                )

            if not supplier_name:
                raise ValueError(
                    "Ghi ná»£ pháº£i tráº£ pháº£i cÃ³ supplier"
                )



        # ==========================================================
        # 6. TÃNH TIá»€N
        # ==========================================================

        total_amount = Decimal(str(price or 0))



        qty = Decimal(str(quantity or 1))

        if qty <= 0:
            raise ValueError("Quantity pháº£i lá»›n hÆ¡n 0")

        unit_price = (
            total_amount / qty
        )

        # ==========================================================
        # 7. Xá»¬ LÃ ACCOUNT
        # ==========================================================

        db_account = None
        account_id = None

        # Ghi ná»£ â†’ chÆ°a thanh toÃ¡n â†’ khÃ´ng gáº¯n tÃ i khoáº£n
        if groq_intent in [
            "ghi_no_phai_thu",
            "ghi_no_khach_hang",
            "ghi_no_phai_tra",
            "ghi_no_nha_cung_cap"
        ]:
            account_id = None

        else:
            # CÃ³ thanh toÃ¡n â†’ xÃ¡c Ä‘á»‹nh tÃ i khoáº£n
            if payment_method:

                payment_lower = (
                    str(payment_method)
            .lower()
                    .strip()
                )

                if "tiá»n máº·t" in payment_lower:
                    acc_type = "CASH"

                elif (
                    "chuyá»ƒn khoáº£n" in payment_lower
                    or "ngÃ¢n hÃ ng" in payment_lower
                ):
                    acc_type = "BANK"

                elif (
                    "momo" in payment_lower
                    or "vÃ­" in payment_lower
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
                        name=f"TÃ i khoáº£n {acc_type}",
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
            "ChÆ°a thanh toÃ¡n"
            if groq_intent in ["ghi_no_phai_thu", "ghi_no_khach_hang", "ghi_no_phai_tra", "ghi_no_nha_cung_cap"]
        else "ÄÃ£ thanh toÃ¡n"
)

        # ==========================================================
        # 11. Táº O TRANSACTION
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

        # QUAN TRá»ŒNG:
        # láº¥y transaction_id trÆ°á»›c khi táº¡o cÃ¡c báº£ng phá»¥

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

        # Chá»‰ táº¡o TransactionDetail náº¿u cÃ³ product

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

            # BÃN HÃ€NG + ÄÃƒ THANH TOÃN
            if (
                groq_intent == "ban_hang"
            ):

                db_account.balance += total_amount

            # THU TIá»€N
            elif groq_intent == "thu_tien":

                db_account.balance += total_amount

            # THU Ná»¢
            elif groq_intent == "thu_no_phai_thu":

                db_account.balance += total_amount
            elif groq_intent == "thu_no_khach_hang":

                db_account.balance += total_amount

            # NHáº¬P HÃ€NG + ÄÃƒ THANH TOÃN
            elif (
                groq_intent == "nhap_hang"
            ):

                db_account.balance -= total_amount

            # CHI TIá»€N
            elif groq_intent == "chi_tien":

                db_account.balance -= total_amount

            # TRáº¢ Ná»¢
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
            # BÃN HÃ€NG â†’ XUáº¤T KHO
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
                        f"Sáº£n pháº©m '{product.name}' khÃ´ng Ä‘á»§ tá»“n kho"
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
                    note="Xuáº¥t kho do bÃ¡n hÃ ng"
                )

                db.add(inventory)

            # -----------------------------
            # NHáº¬P HÃ€NG â†’ NHáº¬P KHO
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

                    note="Nháº­p kho tá»« giao dá»‹ch nháº­p hÃ ng"
                )

                db.add(inventory)

        db.flush()

        # ==========================================================
        # 15. Táº O DEBT
        # ==========================================================

        debt = None

        # -----------------------------
        # BÃN HÃ€NG CHÆ¯A THANH TOÃN
        # â†’ KHÃCH Ná»¢ MÃŒNH
        # -----------------------------

        if (
            groq_intent == "ghi_no_khach_hang"
        ):

            if not customer_id:

                raise ValueError(
                    "pháº£i cÃ³ customer"
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
        # NHáº¬P HÃ€NG CHÆ¯A THANH TOÃN
        # â†’ MÃŒNH Ná»¢ NHÃ€ CUNG Cáº¤P
        # -----------------------------

        elif (
            groq_intent == "ghi_no_nha_cung_cap"

        ):

            if not supplier_id:

                raise ValueError(
                    "pháº£i cÃ³ supplier"
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
        # GHI Ná»¢ PHáº¢I THU
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
        # GHI Ná»¢ PHáº¢I TRáº¢
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
        # 16. COMMIT TOÃ€N Bá»˜
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
            "KhÃ´ng tÃ¬m tháº¥y giao dá»‹ch"
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
