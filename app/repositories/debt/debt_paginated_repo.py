from typing import Optional, List, Tuple, Any, Dict
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail


class DebtPaginatedRepository:

    @staticmethod
    def get_summary_by_user(user_id: int, db: Session) -> Dict[str, Any]:
        rec = (
            db.query(
                func.coalesce(func.sum(Debt.remaining_debt), 0).label("total_remaining"),
                func.count(Debt.debt_id).label("count")
            )
            .filter(
                Debt.user_id == user_id,
                Debt.direction == "RECEIVABLE",
                Debt.status != "PAID"
            )
            .first()
        )
        pay = (
            db.query(
                func.coalesce(func.sum(Debt.remaining_debt), 0).label("total_remaining"),
                func.count(Debt.debt_id).label("count")
            )
            .filter(
                Debt.user_id == user_id,
                Debt.direction == "PAYABLE",
                Debt.status != "PAID"
            )
            .first()
        )
        return {
            "receivable": {
                "total_remaining": float(rec.total_remaining) if rec and rec.total_remaining is not None else 0.0,
                "count": int(rec.count) if rec and rec.count is not None else 0
            },
            "payable": {
                "total_remaining": float(pay.total_remaining) if pay and pay.total_remaining is not None else 0.0,
                "count": int(pay.count) if pay and pay.count is not None else 0
            }
        }

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
    ) -> Tuple[List[Debt], int]:
        query = db.query(Debt).filter(Debt.user_id == user_id)
        if direction:
            query = query.filter(Debt.direction == direction.upper())
        if status:
            query = query.filter(Debt.status == status.upper())
        if customer_id is not None:
            query = query.filter(Debt.customer_id == customer_id)
        if supplier_id is not None:
            query = query.filter(Debt.supplier_id == supplier_id)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = (
                query.outerjoin(Customer, Debt.customer_id == Customer.customer_id)
                .outerjoin(Supplier, Debt.supplier_id == Supplier.supplier_id)
            )
            if direction and direction.upper() == "RECEIVABLE":
                query = query.filter(Customer.customer_name.ilike(search_pattern))
            elif direction and direction.upper() == "PAYABLE":
                query = query.filter(Supplier.supplier_name.ilike(search_pattern))
            else:
                query = query.filter(
                    or_(
                        Customer.customer_name.ilike(search_pattern),
                        Supplier.supplier_name.ilike(search_pattern)
                    )
                )

        total = query.count()
        offset = (page - 1) * limit
        results = (
            query.options(
                joinedload(Debt.customer),
                joinedload(Debt.supplier),
                joinedload(Debt.transaction).joinedload(Transaction.intent),
                joinedload(Debt.transaction)
                .selectinload(Transaction.transaction_detail)
                .joinedload(TransactionDetail.product),
            )
            .order_by(Debt.created_at.desc(), Debt.debt_id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return results, total

    @staticmethod
    def get_payments_by_debt_id(
        debt_id: int,
        user_id: int,
        db: Session
    ) -> Optional[List[DebtPayment]]:
        debt = db.query(Debt).filter(Debt.debt_id == debt_id, Debt.user_id == user_id).first()
        if not debt:
            return None
        return (
            db.query(DebtPayment)
            .filter(DebtPayment.debt_id == debt_id)
            .options(joinedload(DebtPayment.account))
            .order_by(
                DebtPayment.payment_date.desc(),
                DebtPayment.created_at.desc(),
                DebtPayment.payment_id.desc()
            )
            .all()
        )
