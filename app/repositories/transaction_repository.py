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
        page: int,
        limit: int
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
        total = db.scalar(count_stmt) or 0

        offset = (page - 1) * limit

        paginated_stmt = (
            stmt
            .order_by(
                desc(Transaction.transaction_date)
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