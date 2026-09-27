from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.services.debt_service import DebtService
from app.services.websocket_manager import trigger_report_update


class DebtQueryController:

    @staticmethod
    def get_all_debts(
        user_id: int,
        db: Session,
        name: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return DebtService.get_all_debts(
            user_id=user_id,
            db=db,
            name=name,
            direction=direction,
            status=status
        )

    @staticmethod
    def get_summary(user_id: int, db: Session) -> Dict[str, Any]:
        return DebtService.get_summary(user_id=user_id, db=db)

    @staticmethod
    def get_debts_paginated(
        user_id: int,
        db: Session,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        return DebtService.get_debts_paginated(
            user_id=user_id,
            db=db,
            direction=direction,
            status=status,
            search=search,
            customer_id=customer_id,
            supplier_id=supplier_id,
            page=page,
            limit=limit
        )

    @staticmethod
    def get_debt_detail(debt_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        return DebtService.get_debt_detail(debt_id=debt_id, user_id=user_id, db=db)

    @staticmethod
    def get_payment_history(debt_id: int, user_id: int, db: Session) -> List[Dict[str, Any]]:
        return DebtService.get_payment_history(debt_id=debt_id, user_id=user_id, db=db)

    @staticmethod
    def pay_debt_exact(
        debt_id: int,
        user_id: int,
        account_id: int,
        amount: float,
        db: Session,
        payment_date: Optional[datetime] = None,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        res = DebtService.pay_debt_exact(
            debt_id=debt_id,
            user_id=user_id,
            account_id=account_id,
            amount=amount,
            payment_date=payment_date,
            note=note,
            db=db
        )
        try:
            trigger_report_update(user_id=user_id, affected=["debt", "balance"])
        except Exception:
            pass
        return res
