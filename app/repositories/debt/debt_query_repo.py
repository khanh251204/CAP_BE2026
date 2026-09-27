from typing import Optional, List
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.repositories.debt.debt_paginated_repo import DebtPaginatedRepository


class DebtQueryRepository(DebtPaginatedRepository):

    @staticmethod
    def get_by_id(debt_id: int, db: Session):
        return db.query(
            Debt,
            Customer.customer_name.label("customer_name"),
            Supplier.supplier_name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            Debt.debt_id == debt_id,
        ).first()

    @staticmethod
    def get_debt_by_id_and_user(
        debt_id: int,
        user_id: int,
        db: Session,
        direction: Optional[str] = None,
        for_update: bool = False
    ) -> Optional[Debt]:
        query = (
            db.query(Debt)
            .options(
                joinedload(Debt.customer),
                joinedload(Debt.supplier),
                joinedload(Debt.payments).joinedload(DebtPayment.account),
                joinedload(Debt.transaction).joinedload(Transaction.intent),
                joinedload(Debt.transaction)
                .selectinload(Transaction.transaction_detail)
                .joinedload(TransactionDetail.product),
            )
            .filter(
                Debt.debt_id == debt_id,
                Debt.user_id == user_id,
            )
        )
        if direction:
            query = query.filter(Debt.direction == direction)
        if for_update:
            query = query.with_for_update()
        return query.first()

    @staticmethod
    def get_customer_debts(
        user_id: int,
        db: Session,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ):
        query = db.query(
            Debt,
            Customer.customer_name.label("customer_name")
        ).join(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).filter(
            Debt.user_id == user_id,
            Debt.direction == "RECEIVABLE"
        )
        if customer_id is not None:
            query = query.filter(Debt.customer_id == customer_id)
        if status:
            query = query.filter(Debt.status == status.upper())
        if search:
            query = query.filter(Customer.customer_name.ilike(f"%{search}%"))
        return query.order_by(Debt.created_at.desc()).all()

    @staticmethod
    def get_supplier_debts(
        user_id: int,
        db: Session,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ):
        query = db.query(
            Debt,
            Supplier.supplier_name.label("supplier_name")
        ).join(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            Debt.user_id == user_id,
            Debt.direction == "PAYABLE"
        )
        if supplier_id is not None:
            query = query.filter(Debt.supplier_id == supplier_id)
        if status:
            query = query.filter(Debt.status == status.upper())
        if search:
            query = query.filter(Supplier.supplier_name.ilike(f"%{search}%"))
        return query.order_by(Debt.created_at.desc()).all()

    @staticmethod
    def get_all_by_user(
        user_id: int,
        db: Session,
        name: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ):
        query = db.query(
            Debt,
            Customer.customer_name.label("customer_name"),
            Supplier.supplier_name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            Debt.user_id == user_id
        )
        if direction:
            query = query.filter(Debt.direction == direction.upper())
        if status:
            query = query.filter(Debt.status == status.upper())
        if name:
            if name.lower() == "customer":
                query = query.filter(Debt.customer_id.isnot(None))
            elif name.lower() == "supplier":
                query = query.filter(Debt.supplier_id.isnot(None))
            elif name.upper() in ["RECEIVABLE", "PAYABLE"]:
                query = query.filter(Debt.direction == name.upper())
            else:
                query = query.filter(
                    or_(
                        Customer.customer_name.ilike(f"%{name}%"),
                        Supplier.supplier_name.ilike(f"%{name}%")
                    )
                )
        return query.order_by(Debt.created_at.desc()).all()

    @staticmethod
    def get_by_user_id(user_id: int, db: Session):
        return db.query(
            Debt,
            Customer.customer_name.label("customer_name"),
            Supplier.supplier_name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            Debt.user_id == user_id,
        ).order_by(Debt.created_at.desc()).all()

    @staticmethod
    def search_by_name(name: str, db: Session):
        return db.query(
            Debt,
            Customer.customer_name.label("customer_name"),
            Supplier.supplier_name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            or_(
                Customer.customer_name.ilike(f"%{name}%"),
                Supplier.supplier_name.ilike(f"%{name}%")
            )
        ).all()

    @staticmethod
    def get_customer_by_id(customer_id: int, db: Session):
        return db.query(Customer).filter(Customer.customer_id == customer_id).first()

    @staticmethod
    def get_supplier_by_id(supplier_id: int, db: Session):
        return db.query(Supplier).filter(Supplier.supplier_id == supplier_id).first()

    @staticmethod
    def get_open_debts_by_customer_and_user(
        db: Session,
        customer_id: int,
        user_id: int,
        direction: str = "RECEIVABLE",
        order_by: str = "created_at asc",
        for_update: bool = False,
    ) -> List[Debt]:
        query = (
            db.query(Debt)
            .options(
                joinedload(Debt.customer),
                joinedload(Debt.transaction),
            )
            .filter(
                Debt.customer_id == customer_id,
                Debt.user_id == user_id,
                Debt.direction == direction,
                Debt.status.in_(["UNPAID", "PARTIAL"]),
            )
        )
        if for_update:
            query = query.with_for_update()
        return query.order_by(Debt.created_at.asc(), Debt.debt_id.asc()).all()

    @staticmethod
    def get_open_debts_by_supplier_and_user(
        db: Session,
        supplier_id: int,
        user_id: int,
        direction: str = "PAYABLE",
        order_by: str = "created_at asc",
        for_update: bool = False,
    ) -> List[Debt]:
        query = (
            db.query(Debt)
            .options(
                joinedload(Debt.supplier),
                joinedload(Debt.transaction),
            )
            .filter(
                Debt.supplier_id == supplier_id,
                Debt.user_id == user_id,
                Debt.direction == direction,
                Debt.status.in_(["UNPAID", "PARTIAL"]),
            )
        )
        if for_update:
            query = query.with_for_update()
        return query.order_by(Debt.created_at.asc(), Debt.debt_id.asc()).all()
