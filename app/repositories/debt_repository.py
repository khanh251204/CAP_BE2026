from sqlalchemy.orm import Session
from app.models.debt_model import Debt

from app.models.customer_model import  Customer
class DebtRepository:

    # ==========================================
    # LẤY 1 DEBT
    # ==========================================

    @staticmethod
    def get_by_id(
        debt_id: int,
        db: Session
    ):
        return db.query(Debt).filter(
            Debt.debt_id == debt_id,
            Debt.is_active == True
        ).first()


    # ==========================================
    # LẤY TẤT CẢ
    # ==========================================

    @staticmethod
    def get_all_by_user(
        user_id : int,
        db: Session
    ):
        return db.query(Debt,Customer.name.label("customer_name")
        ).outerjoin(
        Customer,
        Debt.customer_id == Customer.customer_id
    ).filter(
        Debt.user_id == user_id
    ).all()
    # ==========================================
    # LẤY DEBT THEO ID
    # ==========================================
    @staticmethod
    def get_by_id(
        debt_id:int,
        db:Session
    ):
        return db.query(
            Debt,
            Customer.name.label("customer_name")
        ).outerjoin(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).filter(
            Debt.debt_id == debt_id
        ).first()


    # ==========================================
    # LẤY THEO USER
    # ==========================================

    @staticmethod
    def get_by_user_id(
        user_id: int,
        db: Session
    ):
        return db.query(Debt).filter(
            Debt.user_id == user_id).all()


    # ==========================================
    # TÌM KIẾM THEO TÊN
    # ==========================================

    @staticmethod
    def search_by_name(
        name: str,
        db: Session
    ):
        return db.query(Debt,
            Customer.name.label("customer_name")
        ).join(
            Customer,
            Debt.customer_id == Customer.customer_id
        ).filter(
            Customer.name.ilike(f"%{name}%")
        ).all()


    # ==========================================
    # TÌM THEO tên
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

        debt.is_active = False

        db.commit()
        db.refresh(debt)

        return debt

    