from app.services.transaction_service import (
    TransactionService
)


class TransactionController:

    @staticmethod
    def get_transactions(
        db,
        user_id: int,
        page: int,
        limit: int
    ):

        return TransactionService.get_transactions(
            db=db,
            user_id=user_id,
            page=page,
            limit=limit
        )

    @staticmethod
    def get_transaction_detail(
        db,
        user_id: int,
        transaction_id: int
    ):

        return TransactionService.get_transaction_detail(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )