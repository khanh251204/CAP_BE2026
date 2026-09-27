from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, or_
from datetime import datetime

from app.models.customer_model import Customer
from app.models.debt_model import Debt
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail


class CustomerRepository:

    @staticmethod
    def create(customer: Customer, db: Session) -> Customer:
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def get_by_id_and_user(customer_id: int, user_id: int, db: Session) -> Optional[Customer]:
        return db.query(Customer).filter(
            Customer.customer_id == customer_id,
            Customer.user_id == user_id
        ).first()

    @staticmethod
    def get_list_by_user(
        user_id: int,
        db: Session,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[Customer], int]:
        query = db.query(Customer).filter(Customer.user_id == user_id)

        if search:
            s = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Customer.customer_name.ilike(s),
                    Customer.phone_number.ilike(s)
                )
            )

        total = query.count()
        offset = (page - 1) * limit
        items = query.order_by(Customer.created_at.desc(), Customer.customer_id.desc()).offset(offset).limit(limit).all()
        return items, total

    @staticmethod
    def update(customer: Customer, db: Session) -> Customer:
        customer.updated_at = datetime.now()
        db.commit()
        db.refresh(customer)
        return customer

    @staticmethod
    def delete(customer: Customer, db: Session) -> bool:
        db.delete(customer)
        db.commit()
        return True

    @staticmethod
    def has_associated_records(customer_id: int, user_id: int, db: Session) -> bool:
        has_debts = db.query(Debt).filter(
            Debt.customer_id == customer_id,
            Debt.user_id == user_id
        ).first() is not None

        has_transactions = db.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.user_id == user_id
        ).first() is not None

        return has_debts or has_transactions

    @staticmethod
    def get_customer_debt_summary(customer_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        debts = db.query(Debt).filter(
            Debt.customer_id == customer_id,
            Debt.user_id == user_id,
            Debt.direction == "RECEIVABLE"
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
    def get_customer_debts_with_details(customer_id: int, user_id: int, db: Session) -> List[Debt]:
        return (
            db.query(Debt)
            .filter(
                Debt.customer_id == customer_id,
                Debt.user_id == user_id,
                Debt.direction == "RECEIVABLE"
            )
            .options(
                joinedload(Debt.customer),
                joinedload(Debt.transaction)
                .selectinload(Transaction.transaction_detail)
                .joinedload(TransactionDetail.product)
            )
            .order_by(Debt.created_at.desc(), Debt.debt_id.desc())
            .all()
        )
