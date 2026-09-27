from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.debt_model import Debt
from app.repositories.debt_repository import DebtRepository


class DebtTransactionMixin:
    @staticmethod
    def create_receivable_debt_for_transaction(
        db: Session,
        user_id: int,
        customer_id: int,
        transaction_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        """
        Ghi nhận công nợ phải thu (RECEIVABLE) phát sinh từ giao dịch bán hàng.
        """
        return DebtRepository.create_receivable_debt(
            db=db,
            transaction_id=transaction_id,
            user_id=user_id,
            customer_id=customer_id,
            amount=amount,
            status=status,
            flush_only=flush_only,
        )

    @staticmethod
    def create_payable_debt_for_transaction(
        db: Session,
        user_id: int,
        supplier_id: int,
        transaction_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        """
        Ghi nhận công nợ phải trả (PAYABLE) phát sinh từ giao dịch nhập hàng.
        """
        return DebtRepository.create_payable_debt(
            db=db,
            transaction_id=transaction_id,
            user_id=user_id,
            supplier_id=supplier_id,
            amount=amount,
            status=status,
            flush_only=flush_only,
        )
