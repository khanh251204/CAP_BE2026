from decimal import Decimal
from typing import Optional, List, Tuple, Any, Dict
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.product_model import Product
from app.models.intent_model import Intent


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

    # ==========================================
    # LẤY SUPPLIER THUỘC USER
    # ==========================================
    @staticmethod
    def get_supplier_by_id_and_user(
        supplier_id: int,
        user_id: int,
        db: Session
    ) -> Optional[Supplier]:
        return db.query(Supplier).filter(
            Supplier.supplier_id == supplier_id,
            Supplier.user_id == user_id
        ).first()

    @staticmethod
    def get_supplier_by_name_and_user(
        supplier_name: str,
        user_id: int,
        db: Session
    ) -> Optional[Supplier]:
        return db.query(Supplier).filter(
            Supplier.user_id == user_id,
            Supplier.supplier_name.ilike(f"%{supplier_name}%")
        ).first()

    @staticmethod
    def create_supplier(
        supplier: Supplier,
        db: Session,
        flush_only: bool = False
    ) -> Supplier:
        db.add(supplier)
        if flush_only:
            db.flush()
            db.refresh(supplier)
        else:
            db.commit()
            db.refresh(supplier)
        return supplier

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
        db: Session,
        for_update: bool = False
    ) -> Optional[Account]:
        query = db.query(Account).filter(
            Account.account_id == account_id,
            Account.user_id == user_id,
            Account.is_active == True,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

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
    # LẤY CÔNG NỢ NHÀ CUNG CẤP (PAYABLE)
    # ==========================================
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

    @staticmethod
    def create_receivable_debt(
        db: Session,
        transaction_id: int,
        user_id: int,
        customer_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        debt = Debt(
            transaction_id=transaction_id,
            user_id=user_id,
            customer_id=customer_id,
            supplier_id=None,
            direction="RECEIVABLE",
            original_amount=amount,
            remaining_debt=amount,
            status=status,
        )
        db.add(debt)
        if flush_only:
            db.flush()
            db.refresh(debt)
        else:
            db.commit()
            db.refresh(debt)
        return debt

    @staticmethod
    def create_payable_debt(
        db: Session,
        transaction_id: int,
        user_id: int,
        supplier_id: int,
        amount: Decimal,
        status: str = "UNPAID",
        flush_only: bool = True,
    ) -> Debt:
        debt = Debt(
            transaction_id=transaction_id,
            user_id=user_id,
            supplier_id=supplier_id,
            customer_id=None,
            direction="PAYABLE",
            original_amount=amount,
            remaining_debt=amount,
            status=status,
        )
        db.add(debt)
        if flush_only:
            db.flush()
            db.refresh(debt)
        else:
            db.commit()
            db.refresh(debt)
        return debt

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

    # ==========================================
    # DASHBOARD SUMMARY (Mục 6.1)
    # ==========================================
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

    # ==========================================
    # PHÂN TRANG DANH SÁCH DEBT (Mục 6.2)
    # ==========================================
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

    # ==========================================
    # LỊCH SỬ THANH TOÁN (Mục 6.4)
    # ==========================================
    @staticmethod
    def get_payments_by_debt_id(
        debt_id: int,
        user_id: int,
        db: Session
    ) -> Optional[List[DebtPayment]]:
        # Phải kiểm tra ownership thông qua Debt.user_id
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