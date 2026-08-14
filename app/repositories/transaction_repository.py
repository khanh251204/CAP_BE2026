from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.transaction_model import Transaction
from app.models.product_model import Product
from app.models.transactionDetail_model import TransactionDetail
from app.models.transactionDetail_model import (
    TransactionDetail
)


class TransactionRepository:

    @staticmethod
    def get_transactions(
        db: Session,
        page: int,
        limit: int
    ):
        query = db.query(Transaction)

        total = query.count()

        offset = (page - 1) * limit

        transactions = (
            query
            .order_by(
                desc(Transaction.transaction_date)
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return transactions, total

    @staticmethod
    def get_transaction_by_id(
        db: Session,
        transaction_id: int
    ):
        return (
            db.query(Transaction)
            .options(
                joinedload(
                    Transaction.details
                ).joinedload(
                    TransactionDetail.product
                )
            )
            .filter(
                Transaction.transaction_id == transaction_id
            )
            .first()
        )