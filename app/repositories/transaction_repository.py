from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, select, func

from app.models.transaction_model import Transaction
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.product_model import Product
from app.models.intent_model import Intent
from app.models.debt_model import Debt
from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail


class TransactionRepository:
    @staticmethod
    def create_transaction(
        db: Session,
        transaction: Transaction
    ) -> Transaction:
        db.add(transaction)
        db.flush()
        db.refresh(transaction)
        return transaction

    @staticmethod
    def create_transaction_detail(
        db: Session,
        detail: TransactionDetail
    ) -> TransactionDetail:
        db.add(detail)
        db.flush()
        db.refresh(detail)
        return detail  

    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 20,
        intent_type: Optional[str] = None,
        intent_name: Optional[str] = None,
    ):
        stmt = (
            select(Transaction)
            .options(
                joinedload(
                    Transaction.transaction_detail
                ).joinedload(
                    TransactionDetail.product
                ),
                joinedload(Transaction.customer),
                joinedload(Transaction.supplier),
                joinedload(Transaction.intent),
                joinedload(Transaction.account),
                joinedload(Transaction.debt),
                joinedload(Transaction.inventory_transaction),
            )
            .filter(
                Transaction.user_id == user_id
            )
        )

        count_stmt = (
            select(func.count())
            .select_from(Transaction)
            .filter(Transaction.user_id == user_id)
        )

        if intent_type:
            stmt = stmt.join(Transaction.intent).filter(
                func.upper(Intent.intent_type) == intent_type.upper()
            )
            count_stmt = count_stmt.join(Transaction.intent).filter(
                func.upper(Intent.intent_type) == intent_type.upper()
            )

        if intent_name:
            if not intent_type:
                stmt = stmt.join(Transaction.intent)
                count_stmt = count_stmt.join(Transaction.intent)
            stmt = stmt.filter(
                Intent.intent_name.ilike(f"%{intent_name.strip()}%")
            )
            count_stmt = count_stmt.filter(
                Intent.intent_name.ilike(f"%{intent_name.strip()}%")
            )

        total = db.scalar(count_stmt) or 0

        offset = (page - 1) * limit

        paginated_stmt = (
            stmt
            .order_by(
                desc(Transaction.transaction_date),
                desc(Transaction.transaction_id)
            )
            .offset(offset)
            .limit(limit)
        )

        transactions = db.scalars(paginated_stmt).unique().all()

        return transactions, total

    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        stmt = (
            select(Transaction)
            .options(
                joinedload(
                    Transaction.transaction_detail
                ).joinedload(
                    TransactionDetail.product
                ),
                joinedload(Transaction.customer),
                joinedload(Transaction.supplier),
                joinedload(Transaction.intent),
                joinedload(Transaction.account)
            )
            .filter(
                Transaction.transaction_id == transaction_id,
                Transaction.user_id == user_id
            )
        )
        return db.scalars(stmt).unique().first()

    @staticmethod
    def get_transaction_for_update(
        db: Session,
        user_id: int,
        transaction_id: int
    ) -> Optional[Transaction]:
        """
        Lấy giao dịch kèm khóa dòng (SELECT ... FOR UPDATE) phục vụ cập nhật.
        Bắt buộc lọc theo user_id (multi-tenant).
        """
        return (
            db.query(Transaction)
            .filter(
                Transaction.transaction_id == transaction_id,
                Transaction.user_id == user_id
            )
            .with_for_update()
            .first()
        )