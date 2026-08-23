from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.transaction_model import Transaction
# from app.models.category_model import Category
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.account_model import Account
from app.models.product_model import Product
from app.models.intent_model import Intent
from app.models.transactionDetail_model import TransactionDetail



class TransactionRepository:

    # @staticmethod
    # def get_transactions(
    #     db: Session,
    #     user_id: int,
    #     page: int,
    #     limit: int
    # ):
    #     query = (
    #         db.query(Transaction)
    #         .options(
    #              joinedload(
    #                 Transaction.transaction_detail
    #             ).joinedload(
    #                 TransactionDetail.product
    #             ),
    #             # joinedload(Transaction.category),
    #             joinedload(Transaction.customer),
    #             joinedload(Transaction.supplier),
    #             joinedload(Transaction.intent),
    #             joinedload(Transaction.account)
    #         )
    #         .filter(
    #             Transaction.user_id == user_id
    #         )
    #     )

    #     total = query.count()

    #     offset = (page - 1) * limit

    #     transactions = (
    #         query
    #         .order_by(
    #             desc(Transaction.transaction_date)
    #         )
    #         .offset(offset)
    #         .limit(limit)
    #         .all()
    #     )

    #     return transactions, total

    # @staticmethod
    # def get_transaction_by_id(
    #     db: Session,
    #     user_id: int,
    #     transaction_id: int
    # ):
    #     return (
    #         db.query(Transaction)
    #         .options(
    #              joinedload(
    #                 Transaction.transaction_detail
    #             ).joinedload(
    #                 TransactionDetail.product
    #             ),
    #             # joinedload(Transaction.category),
    #             joinedload(Transaction.customer),
    #             joinedload(Transaction.supplier),
    #             joinedload(Transaction.intent),
    #             joinedload(Transaction.account)
    #         )
    #         .filter(
    #             Transaction.transaction_id == transaction_id,
    #             Transaction.user_id == user_id
    #         )
    #         .first()
    #     )
    
    @staticmethod
    def create_transaction(
        db: Session,
        transaction: Transaction
    ):

        db.add(transaction)

        db.flush()

        return transaction

    @staticmethod
    def create_transaction_detail(
        db: Session,
        detail: TransactionDetail
    ):

        db.add(detail)

        db.flush()

        return detail  