from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import HTTPException, status

from app.models.closing_period_model import ClosingPeriod
from app.models.closing_transaction_model import ClosingTransaction
from app.models.transaction_model import Transaction
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.services.closing.closing_guard import count_late_transactions


def _late_info(db, r) -> dict:
    """Giao dịch phát sinh sau giờ chốt → kỳ cần chốt lại."""
    try:
        late = count_late_transactions(db, r)
    except Exception:
        late = 0
    return {"late_transaction_count": late, "needs_reclose": late > 0}


class ClosingQueryService:
    @classmethod
    def get_closing_periods(
        cls,
        db: Session,
        user_id: int,
        period_type: Optional[str] = None,
        status_val: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        GET /closing-periods: Lấy danh sách các kỳ đã chốt (snapshot history).
        """
        query = db.query(ClosingPeriod).filter(ClosingPeriod.user_id == user_id)
        if period_type:
            query = query.filter(ClosingPeriod.period_type == period_type.upper())
        if status_val:
            query = query.filter(ClosingPeriod.status == status_val.upper())

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        rows = query.order_by(desc(ClosingPeriod.period_end), desc(ClosingPeriod.closing_id)).offset(offset).limit(page_size).all()

        items = []
        for r in rows:
            tx_count = db.query(func.count(ClosingTransaction.transaction_id)).filter(
                ClosingTransaction.closing_id == r.closing_id
            ).scalar() or 0

            items.append({
                "closing_id": r.closing_id,
                "user_id": r.user_id,
                "period_type": r.period_type,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "total_sales": Decimal(str(r.total_sales or 0)),
                "total_purchase": Decimal(str(r.total_purchase or 0)),
                "total_income": Decimal(str(r.total_income or 0)),
                "total_expense": Decimal(str(r.total_expense or 0)),
                "total_receivable": Decimal(str(r.total_receivable or 0)),
                "total_payable": Decimal(str(r.total_payable or 0)),
                "total_inventory_value": Decimal(str(r.total_inventory_value or 0)),
                "status": r.status,
                "note": r.note,
                "closed_at": r.closed_at.isoformat() if r.closed_at else "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "transaction_count": tx_count,
            **_late_info(db, r)
            })

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total
        }

    @classmethod
    def get_closing_period_detail(
        cls,
        db: Session,
        user_id: int,
        closing_id: int
    ) -> Dict[str, Any]:
        """
        GET /closing-periods/{id}: Lấy chi tiết một kỳ chốt sổ.
        """
        r = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == closing_id,
            ClosingPeriod.user_id == user_id
        ).first()

        if not r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id}."
            )

        tx_count = db.query(func.count(ClosingTransaction.transaction_id)).filter(
            ClosingTransaction.closing_id == r.closing_id
        ).scalar() or 0

        return {
            "closing_id": r.closing_id,
            "user_id": r.user_id,
            "period_type": r.period_type,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "total_sales": Decimal(str(r.total_sales or 0)),
            "total_purchase": Decimal(str(r.total_purchase or 0)),
            "total_income": Decimal(str(r.total_income or 0)),
            "total_expense": Decimal(str(r.total_expense or 0)),
            "total_receivable": Decimal(str(r.total_receivable or 0)),
            "total_payable": Decimal(str(r.total_payable or 0)),
            "total_inventory_value": Decimal(str(r.total_inventory_value or 0)),
            "status": r.status,
            "note": r.note,
            "closed_at": r.closed_at.isoformat() if r.closed_at else "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "transaction_count": tx_count,
            **_late_info(db, r)
        }

    @classmethod
    def get_closing_transactions(
        cls,
        db: Session,
        user_id: int,
        closing_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        GET /closing-periods/{id}/transactions: Danh sách các giao dịch thuộc kỳ chốt sổ.
        """
        closing = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == closing_id,
            ClosingPeriod.user_id == user_id
        ).first()

        if not closing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id}."
            )

        query = db.query(
            Transaction.transaction_id,
            Transaction.transaction_date,
            Intent.intent_name,
            Transaction.total_amount,
            Transaction.payment_status,
            Transaction.input_method,
            Transaction.note,
            Category.category_name,
            Customer.customer_name,
            Supplier.supplier_name
        ).join(ClosingTransaction, Transaction.transaction_id == ClosingTransaction.transaction_id)\
         .outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .outerjoin(Customer, Transaction.customer_id == Customer.customer_id)\
         .outerjoin(Supplier, Transaction.supplier_id == Supplier.supplier_id)\
         .filter(
             ClosingTransaction.closing_id == closing_id,
             Transaction.user_id == user_id
         )

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        rows = query.order_by(desc(Transaction.transaction_date)).offset(offset).limit(page_size).all()

        items = []
        for r in rows:
            items.append({
                "transaction_id": r.transaction_id,
                "transaction_date": r.transaction_date.isoformat() if r.transaction_date else "",
                "intent": r.intent_name,
                "total_amount": Decimal(str(r.total_amount or 0)),
                "payment_status": str(r.payment_status),
                "input_method": str(r.input_method) if r.input_method else None,
                "category_name": r.category_name,
                "customer_name": r.customer_name,
                "supplier_name": r.supplier_name,
                "note": r.note
            })

        return {
            "closing_id": closing_id,
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total
        }
