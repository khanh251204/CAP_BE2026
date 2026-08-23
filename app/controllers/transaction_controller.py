from app.services.transaction_service import (
    TransactionService
)


class TransactionController:

    # @staticmethod
    # def get_transactions(
    #     db,
    #     user_id: int,
    #     page: int,
    #     limit: int
    # ):

    #     return TransactionService.get_transactions(
    #         db=db,
    #         user_id=user_id,
    #         page=page,
    #         limit=limit
    #     )

    # @staticmethod
    # def get_transaction_detail(
    #     db,
    #     user_id: int,
    #     transaction_id: int
    # ):

    #     return TransactionService.get_transaction_detail(
    #         db=db,
    #         user_id=user_id,
    #         transaction_id=transaction_id
    #     )

    @staticmethod
    def save_groq_transaction(
        db,
        user_id: int,
        account_id: int | None,
        groq_result: dict
    ):
        # Gọi thẳng xuống Service để xử lý logic
        return TransactionService.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=account_id,
            groq_result=groq_result
        )


    