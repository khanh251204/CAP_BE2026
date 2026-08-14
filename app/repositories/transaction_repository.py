from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.transaction_model import Transaction


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
            .filter(
                Transaction.transaction_id == transaction_id
            )
            .first()
        )