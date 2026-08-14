from app.services.transaction_service import (
    TransactionService
)


class TransactionController:

    @staticmethod
    def get_transactions(
        db,
        page: int,
        limit: int
    ):

        return TransactionService.get_transactions(
            db=db,
            page=page,
            limit=limit
        )

    @staticmethod
    def get_transaction_detail(
        db,
        transaction_id: int
    ):

        return TransactionService.get_transaction_detail(
            db=db,
            transaction_id=transaction_id
        )