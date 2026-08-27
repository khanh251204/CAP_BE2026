from app.services.transaction_service import (
    TransactionService
)
from sqlalchemy.orm import Session


class TransactionController:

    # lưu
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
    

    # list
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
    def get_transaction_by_id(
        db,
        user_id: int,
        transaction_id: int
    ):

        return TransactionService.get_transaction_by_id(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )

    @staticmethod
    def update_transaction(
        db,
        user_id: int,
        transaction_id: int,
        data: dict
    ):
        return TransactionService.update_transaction(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id,
            data=data
        )


    @staticmethod
    def delete_transaction(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        return TransactionService.delete_transaction(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )



    