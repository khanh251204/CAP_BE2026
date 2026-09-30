from datetime import datetime
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.services.debt_service import DebtService
from app.services.websocket_manager import trigger_report_update


class SupplierDebtController:

    @staticmethod
    def create_supplier_debt(
        db: Session,
        user_id: int,
        supplier_id: int,
        total_debt: float,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        res = DebtService.create_supplier_debt(
            db=db,
            user_id=user_id,
            supplier_id=supplier_id,
            total_debt=total_debt,
            transaction_id=transaction_id,
            note=note,
            input_method=input_method,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "payable"])
        except Exception:
            pass
        return res

    @staticmethod
    def pay_supplier_debt(
        db: Session,
        user_id: int,
        account_id: int,
        amount: float,
        debt_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
        input_method: Optional[str] = "MANUAL",
    ) -> Dict[str, Any]:
        res = DebtService.pay_supplier_debt(
            db=db,
            user_id=user_id,
            debt_id=debt_id,
            supplier_id=supplier_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
            input_method=input_method,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "payable", "balance"])
        except Exception:
            pass
        return res

    @staticmethod
    def get_supplier_debts(
        user_id: int,
        db: Session,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return DebtService.get_supplier_debts(
            user_id=user_id,
            db=db,
            supplier_id=supplier_id,
            status=status,
            search=search
        )

    @staticmethod
    def pay_supplier_debts_fifo(
        db: Session,
        user_id: int,
        supplier_id: int,
        account_id: int,
        amount: float,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        res = DebtService.pay_supplier_debts_fifo(
            db=db,
            user_id=user_id,
            supplier_id=supplier_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "payable", "balance"])
        except Exception:
            pass
        return res
