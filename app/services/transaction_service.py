from math import ceil

from app.repositories.transaction_repository import (
    TransactionRepository
)


class TransactionService:

    @staticmethod
    def get_transactions(
        db,
        page: int,
        limit: int
    ):

        transactions, total = (
            TransactionRepository.get_transactions(
                db=db,
                page=page,
                limit=limit
            )
        )

        total_pages = (
            ceil(total / limit)
            if total > 0
            else 0
        )

        data = []

        for transaction in transactions:

            data.append({
                "transaction_id": transaction.transaction_id,
                "type": transaction.type,
                "intent": transaction.intent,
                "total_amount": transaction.total_amount,
                "payment_status": transaction.payment_status,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                )
            })

        return {
            "success": True,
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            }
        }

    @staticmethod
    def get_transaction_detail(
        db,
        transaction_id: int
    ):

        transaction = (
            TransactionRepository
            .get_transaction_by_id(
                db=db,
                transaction_id=transaction_id
            )
        )

        if not transaction:
            return {
                "success": False,
                "message": "Không tìm thấy giao dịch"
            }

        return {
            "success": True,
            "data": {
                "transaction_id": transaction.transaction_id,
                "type": transaction.type,
                "intent": transaction.intent,
                "total_amount": transaction.total_amount,
                "payment_status": transaction.payment_status,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                )
            }
        }