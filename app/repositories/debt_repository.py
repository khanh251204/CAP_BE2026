from sqlalchemy.orm import Session

from app.models.debt_model import Debt
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier


class DebtRepository:

    # ==========================================
    # LẤY 1 DEBT
    # ==========================================

    @staticmethod
    def get_by_id(
        debt_id: int,
        db: Session
    ):
        return db.query(
            Debt,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name")
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
    # LẤY TẤT CẢ
    # ==========================================

    @staticmethod
    def get_all_by_user(
        user_id: int,
        db: Session
    ):
        return db.query(
            Debt,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            Debt.user_id == user_id,
        ).all()

    # ==========================================
    # LẤY THEO USER
    # ==========================================

    @staticmethod
    def get_by_user_id(
        user_id: int,
        db: Session
    ):
        return db.query(
            Debt,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            Debt.user_id == user_id,
        ).all()

    # ==========================================
    # TÌM KIẾM THEO TÊN
    # CUSTOMER + SUPPLIER
    # ==========================================

    @staticmethod
    def search_by_name(
        name: str,
        db: Session
    ):
        return db.query(
            Debt,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).outerjoin(
            Supplier,
            Debt.supplier_id == Supplier.supplier_id
        ).filter(
            (
                Customer.name.ilike(f"%{name}%")
                |
                Supplier.name.ilike(f"%{name}%")
            )
        ).all()

    # ==========================================
    # LẤY CUSTOMER
    # ==========================================

    @staticmethod
    def get_customer_by_id(
        customer_id: int,
        db: Session
    ):
        return db.query(
            Customer
        ).filter(
            Customer.customer_id == customer_id
        ).first()

    # ==========================================
    # LẤY SUPPLIER
    # ==========================================

    @staticmethod
    def get_supplier_by_id(
        supplier_id: int,
        db: Session
    ):
        return db.query(
            Supplier
        ).filter(
            Supplier.supplier_id == supplier_id
        ).first()

    # ==========================================
    # THÊM
    # ==========================================

    @staticmethod
    def create(
        debt: Debt,
        db: Session
    ):

        db.add(debt)
        db.commit()
        db.refresh(debt)

        return debt

    # ==========================================
    # SỬA
    # ==========================================

    @staticmethod
    def update(
        debt: Debt,
        db: Session
    ):

        db.commit()
        db.refresh(debt)

        return debt

    # ==========================================
    # XÓA MỀM
    # ==========================================

    @staticmethod
    def delete(
        debt: Debt,
        db: Session
    ):

        #debt.is_active = False

        db.commit()
        db.refresh(debt)

        return debt