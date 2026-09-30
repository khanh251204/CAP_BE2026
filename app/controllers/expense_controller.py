from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.expense_service import ExpenseService


class ExpenseController:
    """
    ExpenseController — Điều phối các nghiệp vụ chi phí cho API và MCP Tools.
    """

    @staticmethod
    def create_expense(
        db: Session,
        user_id: int,
        amount: float,
        category_name: Optional[str] = None,
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        note: Optional[str] = None,
        payment_status: Optional[str] = "PAID",
        transaction_date: Optional[datetime] = None,
        input_text: Optional[str] = None,
        input_method: Optional[str] = "MANUAL"
    ) -> Dict[str, Any]:
        return ExpenseService.create_expense(
            db=db,
            user_id=user_id,
            amount=amount,
            category_name=category_name,
            category_id=category_id,
            account_id=account_id,
            note=note,
            payment_status=payment_status,
            transaction_date=transaction_date,
            input_text=input_text,
            input_method=input_method
        )
