from decimal import Decimal
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.account_model import Account
from app.models.debt_model import Debt
from app.models.inventory_model import InventoryTransaction
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.product_model import Product


class InventoryRepository:

    def __init__(self, db: Session):
        self.db = db

    # =========================================================
    # INVENTORY
    # =========================================================

    def get_latest_stock(
        self,
        user_id: int,
        product_id: int
    ) -> Decimal:

        latest = (
            self.db.query(
                InventoryTransaction.quantity_after
            )
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id,
            )
            .order_by(
                InventoryTransaction.inventory_transaction_id.desc()
            )
            .first()
        )

        return (
            Decimal(str(latest[0]))
            if latest
            else Decimal("0.0")
        )

    # =========================================================
    # TRANSACTION - IMPORT
    # =========================================================

    def create_transaction(
        self,
        user_id: int,
        supplier_id: Optional[int],
        account_id: Optional[int],
        total_amount: Decimal,
        payment_status: str = "PAID",
        input_method: str = "MANUAL",
        note: Optional[str] = None,
        input_text: Optional[str] = None,
        intent_id: Optional[int] = None,
    ) -> Transaction:

        now = datetime.now()

        transaction = Transaction(
            user_id=user_id,
            supplier_id=supplier_id,
            account_id=account_id,
            intent_id=intent_id,
            total_amount=total_amount,
            payment_status=payment_status,
            input_method=input_method,
            input_text=input_text,
            note=note,
            transaction_date=now,
            created_at=now,
            updated_at=now,
        )

        self.db.add(transaction)
        self.db.flush()

        return transaction

    # =========================================================
    # TRANSACTION - SALE
    # =========================================================

    def create_sale_transaction(
        self,
        user_id: int,
        customer_id: Optional[int],
        account_id: Optional[int],
        total_amount: Decimal,
        payment_status: str = "PAID",
        input_method: str = "MANUAL",
        input_text: Optional[str] = None,
        note: Optional[str] = None,
        intent_id: Optional[int] = None,
    ) -> Transaction:

        now = datetime.now()

        transaction = Transaction(
            user_id=user_id,
            customer_id=customer_id,
            account_id=account_id,
            intent_id=intent_id,
            total_amount=total_amount,
            payment_status=payment_status,
            input_method=input_method,
            input_text=input_text,
            note=note,
            transaction_date=now,
            created_at=now,
            updated_at=now,
        )

        self.db.add(transaction)
        self.db.flush()

        return transaction

    # =========================================================
    # TRANSACTION DETAIL
    # =========================================================

    def create_transaction_detail(
        self,
        transaction_id: int,
        product_id: int,
        quantity: Decimal,
        unit: str,
        unit_price: Decimal,
        subtotal: Decimal,
    ) -> TransactionDetail:

        detail = TransactionDetail(
            transaction_id=transaction_id,
            product_id=product_id,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            subtotal=subtotal,
        )

        self.db.add(detail)

        return detail

    # =========================================================
    # INVENTORY TRANSACTION
    # =========================================================

    def create_inventory_transaction(
        self,
        user_id: int,
        product_id: int,
        transaction_id: int,
        type: str,
        quantity: Decimal,
        unit: Optional[str] = "",
        quantity_before: Decimal = Decimal("0.0"),
        quantity_after: Decimal = Decimal("0.0"),
        note: Optional[str] = None,
    ) -> InventoryTransaction:

        now = datetime.now()

        inventory_tx = InventoryTransaction(
            user_id=user_id,
            product_id=product_id,
            transaction_id=transaction_id,
            inventory_type=type,
            quantity=quantity,
            unit=unit,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            note=note,
            created_at=now,
        )

        self.db.add(inventory_tx)

        return inventory_tx

    # =========================================================
    # ACCOUNT
    # =========================================================

    def increase_account_balance(
        self,
        user_id: int,
        account_id: int,
        amount: Decimal
    ) -> None:

        account = (
            self.db.query(Account)
            .filter(
                Account.account_id == account_id,
                Account.user_id == user_id,
            )
            .first()
        )

        if account:
            account.balance = (
                Decimal(str(account.balance))
                + amount
            )

    # =========================================================
    # DEBT - CUSTOMER
    # =========================================================

    def create_receivable_debt(
        self,
        transaction_id: int,
        user_id: int,
        customer_id: int,
        amount: Decimal,
        status: str = "UNPAID",
    ) -> Debt:

        debt = Debt(
            transaction_id=transaction_id,
            user_id=user_id,
            customer_id=customer_id,
            direction="RECEIVABLE",
            original_amount=amount,
            remaining_amount=amount,
            status=status,
        )

        self.db.add(debt)

        return debt

    # =========================================================
    # PRODUCT
    # =========================================================

    def get_product_id_by_name(
        self,
        user_id: int,
        name: str
    ) -> Optional[int]:

        if not name:
            return None

        clean_name = name.strip()

        # Exact match
        product = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_name == clean_name,
            )
            .first()
        )

        # Fuzzy match
        if not product:
            product = (
                self.db.query(Product)
                .filter(
                    Product.user_id == user_id,
                    Product.product_name.ilike(
                        f"%{clean_name}%"
                    ),
                )
                .first()
            )

        return (
            product.product_id
            if product
            else None
        )

    def get_product_by_id(
        self,
        user_id: int,
        product_id: int
    ) -> Optional[Product]:

        return (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_id == product_id,
            )
            .first()
        )

    def get_product_price(
        self,
        user_id: int,
        product_id: int
    ) -> Optional[Decimal]:

        product = self.get_product_by_id(
            user_id=user_id,
            product_id=product_id,
        )

        if (
            product
            and product.unit_price is not None
            and float(product.unit_price) > 0
        ):
            return Decimal(
                str(product.unit_price)
            )

        return None

    def get_product_by_name_and_unit(
        self,
        user_id: int,
        name: str,
        unit: str
    ):

        query = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_name.ilike(
                    f"%{name}%"
                ),
            )
        )

        if unit:
            query = query.filter(
                Product.default_unit.ilike(unit)
            )

        return query.first()

    # Compatibility alias
    get_product = get_product_by_id