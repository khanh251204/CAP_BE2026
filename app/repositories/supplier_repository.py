from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, or_
from datetime import datetime

from app.models.supplier_model import Supplier
from app.models.debt_model import Debt
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail


class SupplierRepository:

    @staticmethod
    def create(supplier: Supplier, db: Session) -> Supplier:
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        return supplier

    @staticmethod
    def get_by_id_and_user(supplier_id: int, user_id: int, db: Session) -> Optional[Supplier]:
        return db.query(Supplier).filter(
            Supplier.supplier_id == supplier_id,
            Supplier.user_id == user_id
        ).first()

    @staticmethod
    def get_list_by_user(
        user_id: int,
        db: Session,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[Supplier], int]:
        query = db.query(Supplier).filter(Supplier.user_id == user_id)

        if search:
            s = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Supplier.supplier_name.ilike(s),
                    Supplier.phone_number.ilike(s)
                )
            )

        total = query.count()
        offset = (page - 1) * limit
        items = query.order_by(Supplier.created_at.desc(), Supplier.supplier_id.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def update(supplier: Supplier, db: Session) -> Supplier:
        supplier.updated_at = datetime.now()
        db.commit()
        db.refresh(supplier)
        return supplier

    @staticmethod
    def delete(supplier: Supplier, db: Session) -> bool:
        db.delete(supplier)
        db.commit()
        return True

    @staticmethod
    def has_associated_records(supplier_id: int, user_id: int, db: Session) -> bool:
        has_debts = db.query(Debt).filter(
            Debt.supplier_id == supplier_id,
            Debt.user_id == user_id
        ).first() is not None

        has_transactions = db.query(Transaction).filter(
            Transaction.supplier_id == supplier_id,
            Transaction.user_id == user_id
        ).first() is not None

        return has_debts or has_transactions

    @staticmethod
    def get_supplier_debt_summary(supplier_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        debts = db.query(Debt).filter(
            Debt.supplier_id == supplier_id,
            Debt.user_id == user_id,
            Debt.direction == "PAYABLE"
        ).all()

        total_original = 0.0
        total_remaining = 0.0
        unpaid_count = 0
        partial_count = 0
        paid_count = 0

        for d in debts:
            orig = float(d.original_amount or 0)
            rem = float(d.remaining_debt or 0)
            total_original += orig
            total_remaining += rem

            st = str(d.status).upper()
            if st == "PAID" or rem <= 0:
                paid_count += 1
            elif st == "PARTIAL":
                partial_count += 1
            else:
                unpaid_count += 1

        total_paid = max(0.0, total_original - total_remaining)
        return {
            "total_original": total_original,
            "total_paid": total_paid,
            "total_remaining": total_remaining,
            "unpaid_count": unpaid_count,
            "partial_count": partial_count,
            "paid_count": paid_count
        }

    @staticmethod
    def get_supplier_debts_with_details(supplier_id: int, user_id: int, db: Session) -> List[Debt]:
        return (
            db.query(Debt)
            .filter(
                Debt.supplier_id == supplier_id,
                Debt.user_id == user_id,
                Debt.direction == "PAYABLE"
            )
            .options(
                joinedload(Debt.supplier),
                joinedload(Debt.transaction)
                .selectinload(Transaction.transaction_detail)
                .joinedload(TransactionDetail.product)
            )
            .order_by(Debt.created_at.desc(), Debt.debt_id.desc())
            .all()
        )
