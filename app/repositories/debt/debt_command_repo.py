from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.transaction_model import Transaction


class DebtCommandRepository:

    @staticmethod
    def get_supplier_by_id_and_user(
        supplier_id: int,
        user_id: int,
        db: Session
    ) -> Optional[Supplier]:
        return db.query(Supplier).filter(
            Supplier.supplier_id == supplier_id,
            Supplier.user_id == user_id
        ).first()

    @staticmethod
    def get_supplier_by_name_and_user(
        supplier_name: str,
        user_id: int,
        db: Session
    ) -> Optional[Supplier]:
        return db.query(Supplier).filter(
            Supplier.user_id == user_id,
            Supplier.supplier_name.ilike(f"%{supplier_name}%")
        ).first()

    @staticmethod
    def create_supplier(
        supplier_name: str,
        user_id: int,
        db: Session,
        phone_number: Optional[str] = None
    ) -> Supplier:
        supplier = Supplier(
            user_id=user_id,
            supplier_name=supplier_name,
            phone_number=phone_number
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        return supplier

    @staticmethod
    def get_customer_by_id_and_user(
        customer_id: int,
        user_id: int,
        db: Session
    ) -> Optional[Customer]:
        return db.query(Customer).filter(
            Customer.customer_id == customer_id,
            Customer.user_id == user_id
        ).first()

    @staticmethod
    def get_account_by_id_and_user(
        account_id: int,
        user_id: int,
        db: Session
    ) -> Optional[Account]:
        return db.query(Account).filter(
            Account.account_id == account_id,
            Account.user_id == user_id
        ).first()

    @staticmethod
    def create_debt(
        debt: Debt,
        db: Session,
        flush_only: bool = False
    ) -> Debt:
        db.add(debt)
        if flush_only:
            db.flush()
            db.refresh(debt)
        else:
            db.commit()
            db.refresh(debt)
        return debt

    @staticmethod
    def create(
        debt: Debt,
        db: Session
    ) -> Debt:
        return DebtCommandRepository.create_debt(debt, db, flush_only=False)

    @staticmethod
    def create_receivable_debt(
        db: Session,
        transaction_id: int,
        user_id: int,
        customer_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        debt = Debt(
            transaction_id=transaction_id,
            user_id=user_id,
            customer_id=customer_id,
            supplier_id=None,
            direction="RECEIVABLE",
            original_amount=amount,
            remaining_debt=amount,
            status=status,
        )
        db.add(debt)
        if flush_only:
            db.flush()
            db.refresh(debt)
        else:
            db.commit()
            db.refresh(debt)
        return debt

    @staticmethod
    def create_payable_debt(
        db: Session,
        transaction_id: int,
        user_id: int,
        supplier_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        debt = Debt(
            transaction_id=transaction_id,
            user_id=user_id,
            supplier_id=supplier_id,
            customer_id=None,
            direction="PAYABLE",
            original_amount=amount,
            remaining_debt=amount,
            status=status,
        )
        db.add(debt)
        if flush_only:
            db.flush()
            db.refresh(debt)
        else:
            db.commit()
            db.refresh(debt)
        return debt

    @staticmethod
    def create_payment(
        payment: DebtPayment,
        db: Session,
        flush_only: bool = True
    ) -> DebtPayment:
        db.add(payment)
        if flush_only:
            db.flush()
            db.refresh(payment)
        else:
            db.commit()
            db.refresh(payment)
        return payment

    @staticmethod
    def create_transaction(
        transaction: Transaction,
        db: Session,
        flush_only: bool = True
    ) -> Transaction:
        db.add(transaction)
        if flush_only:
            db.flush()
            db.refresh(transaction)
        else:
            db.commit()
            db.refresh(transaction)
        return transaction

    @staticmethod
    def update(
        debt: Debt,
        db: Session
    ) -> Debt:
        db.commit()
        db.refresh(debt)
        return debt

    @staticmethod
    def delete(
        debt: Debt,
        db: Session
    ) -> Debt:
        db.delete(debt)
        db.commit()
        return debt
