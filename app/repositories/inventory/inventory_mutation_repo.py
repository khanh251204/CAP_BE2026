from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.account_model import Account
from app.models.inventory_model import InventoryTransaction
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail


class InventoryMutationRepository:
    def __init__(self, db: Session):
        self.db = db

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

    def create_inventory_transaction(
        self,
        user_id: int,
        product_id: int,
        transaction_id: Optional[int] = None,
        type: str = "IN",
        quantity: Decimal = Decimal("0.0"),
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
            account.balance = Decimal(str(account.balance)) + amount
