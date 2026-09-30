from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.services.debt_service import DebtService
from app.services.websocket_manager import trigger_report_update


class CustomerDebtController:

    @staticmethod
    def create_customer_debt(
        db: Session,
        user_id: int,
        customer_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        res = DebtService.create_customer_debt(
            db=db,
            user_id=user_id,
            customer_id=customer_id,
            total_debt=total_debt,
            transaction_id=transaction_id,
            note=note,
            input_method=input_method,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable"])
        except Exception:
            pass
        return res

    @staticmethod
    def collect_customer_debt(
        db: Session,
        user_id: int,
        account_id: int,
        amount: float,
        debt_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        res = DebtService.collect_customer_debt(
            db=db,
            user_id=user_id,
            debt_id=debt_id,
            customer_id=customer_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
            input_method=input_method,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable", "balance"])
        except Exception:
            pass
        return res

    @staticmethod
    def get_customer_debts(
        user_id: int,
        db: Session,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return DebtService.get_customer_debts(
            user_id=user_id,
            db=db,
            customer_id=customer_id,
            status=status,
            search=search
        )

    @staticmethod
    def pay_customer_debts_fifo(
        db: Session,
        user_id: int,
        customer_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        res = DebtService.pay_customer_debts_fifo(
            db=db,
            user_id=user_id,
            customer_id=customer_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "receivable", "balance"])
        except Exception:
            pass
        return res
