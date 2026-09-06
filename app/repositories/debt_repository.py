from typing import Optional, List, Tuple
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session, joinedload

from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.transaction_model import Transaction


class DebtRepository:

    # ==========================================
    # LẤY 1 DEBT KÈM CUSTOMER/SUPPLIER THEO ID
    # ==========================================
    @staticmethod
    def get_by_id(
        debt_id: int,
        db: Session
    ):
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

    # ==========================================
    # LẤY 1 DEBT CỤ THỂ THEO USER_ID & DIRECTION
    # ==========================================
    @staticmethod
    def get_debt_by_id_and_user(
        debt_id: int,
        user_id: int,
        db: Session,
        direction: Optional[str] = None
    ) -> Optional[Debt]:
        query = (
            db.query(Debt)
            .options(
                joinedload(Debt.customer),
                joinedload(Debt.payments),
                joinedload(Debt.transaction),
            )
            .filter(
                Debt.debt_id == debt_id,
                Debt.user_id == user_id,
            )
        )
        if direction:
            query = query.filter(Debt.direction == direction)
        return query.first()

    # ==========================================
    # LẤY CUSTOMER THUỘC USER
    # ==========================================
    @staticmethod
    def get_customer_by_id_and_user(
        customer_id: int,
        user_id: int,
        db: Session
    ) -> Optional[Customer]:
        return db.query(Customer).filter(
            Customer.customer_id == customer_id,
            Customer.user_id == user_id
        ).first()

    # ==========================================
    # LẤY ACCOUNT THUỘC USER
    # ==========================================
    @staticmethod
    def get_account_by_id_and_user(
        account_id: int,
        user_id: int,
        db: Session
    ) -> Optional[Account]:
        return db.query(Account).filter(
            Account.account_id == account_id,
            Account.user_id == user_id,
            Account.is_active == True,
        ).first()

    # ==========================================
    # LẤY CÔNG NỢ KHÁCH HÀNG (RECEIVABLE)
    # ==========================================
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

    # ==========================================
    # LẤY TẤT CẢ THEO USER (HỖ TRỢ FILTER NAME)
    # ==========================================
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

    # ==========================================
    # LẤY THEO USER_ID
    # ==========================================
    @staticmethod
    def get_by_user_id(
        user_id: int,
        db: Session
    ):
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

    # ==========================================
    # TÌM KIẾM THEO TÊN (CUSTOMER + SUPPLIER)
    # ==========================================
    @staticmethod
    def search_by_name(
        name: str,
        db: Session
    ):
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

    # ==========================================
    # LẤY CUSTOMER (LEGACY)
    # ==========================================
    @staticmethod
    def get_customer_by_id(
        customer_id: int,
        db: Session
    ):
        return db.query(Customer).filter(
            Customer.customer_id == customer_id
        ).first()

    # ==========================================
    # LẤY SUPPLIER (LEGACY)
    # ==========================================
    @staticmethod
    def get_supplier_by_id(
        supplier_id: int,
        db: Session
    ):
        return db.query(Supplier).filter(
            Supplier.supplier_id == supplier_id
        ).first()

    # ==========================================
    # TẠO MỚI DEBT
    # ==========================================
    @staticmethod
    def create_debt(
        debt: Debt,
        db: Session,
        flush_only: bool = False
    ) -> Debt:
        db.add(debt)
        if flush_only:
            db.flush()
            db.refresh(debt)
        else:
            db.commit()
            db.refresh(debt)
        return debt

    @staticmethod
    def create(
        debt: Debt,
        db: Session
    ) -> Debt:
        return DebtRepository.create_debt(debt, db, flush_only=False)

    # ==========================================
    # TẠO MỚI DEBT PAYMENT
    # ==========================================
    @staticmethod
    def create_payment(
        payment: DebtPayment,
        db: Session,
        flush_only: bool = True
    ) -> DebtPayment:
        db.add(payment)
        if flush_only:
            db.flush()
            db.refresh(payment)
        else:
            db.commit()
            db.refresh(payment)
        return payment

    # ==========================================
    # TẠO MỚI TRANSACTION PHỤC VỤ NỢ
    # ==========================================
    @staticmethod
    def create_transaction(
        transaction: Transaction,
        db: Session,
        flush_only: bool = True
    ) -> Transaction:
        db.add(transaction)
        if flush_only:
            db.flush()
            db.refresh(transaction)
        else:
            db.commit()
            db.refresh(transaction)
        return transaction

    # ==========================================
    # CẬP NHẬT DEBT
    # ==========================================
    @staticmethod
    def update(
        debt: Debt,
        db: Session
    ) -> Debt:
        db.commit()
        db.refresh(debt)
        return debt

    # ==========================================
    # XÓA
    # ==========================================
    @staticmethod
    def delete(
        debt: Debt,
        db: Session
    ) -> Debt:
        db.delete(debt)
        db.commit()
        return debt

    @staticmethod
    def get_open_debts_by_customer_and_user(
        db: Session,
        customer_id: int,
        user_id: int,
        direction: str = "RECEIVABLE",
        order_by: str = "created_at asc",
    ) -> List[Debt]:
        return (
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
            .order_by(Debt.created_at.asc())  # FIFO: cũ nhất trước
            .all()
        )