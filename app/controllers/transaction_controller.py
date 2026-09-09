from sqlalchemy.orm import Session
from app.services.transaction_service import TransactionService
from app.schemas.transaction_schema import TransactionCreateRequest


class TransactionController:

    @staticmethod
    def create_transaction(
        db: Session,
        user_id: int,
        request: TransactionCreateRequest
    ):
        """
        Tạo giao dịch. Tự động nhận diện:
        - Nếu request có `details` hoặc các trường FK ID chuẩn (intent_id, category_id, account_id...)
          thì gọi create_direct_transaction theo đúng docs/erd.md.
        - Nếu request chứa các trường phẳng NLP (product, price, quantity, text...)
          thì gom thành payload và gọi save_groq_transaction.
        """
        is_direct = bool(
            request.details
            or request.category_id is not None
            or request.account_id is not None
            or (request.intent_id is not None and not request.product)
        )

        if is_direct:
            return TransactionService.create_direct_transaction(
                db=db,
                user_id=user_id,
                request=request
            )

        # Chế độ tương thích ngược Flat NLP / Groq Voice
        groq_result_dict = {
            "transaction_analysis": {
                "text": request.text or request.input_text or "",
                "intent": request.intent or "",
                "type": request.type or "",
                "entities": {
                    "product": request.product,
                    "price": request.price or request.total_amount,
                    "quantity": request.quantity,
                    "unit": request.unit,
                    "customer": request.customer,
                    "supplier": request.supplier,
                    "date": request.date or (request.transaction_date.isoformat() if request.transaction_date else None),
                    "payment": request.payment
                }
            }
        }

        return TransactionService.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=request.account_id,
            groq_result=groq_result_dict
        )

    @staticmethod
    def save_groq_transaction(
        db: Session,
        user_id: int,
        account_id: int | None,
        groq_result: dict
    ):
        return TransactionService.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=account_id,
            groq_result=groq_result
        )

    @staticmethod
    def get_transactions(
        db: Session,
        user_id: int,
        page: int = 1,
        limit: int = 10
    ):
        return TransactionService.get_transactions(
            db=db,
            user_id=user_id,
            page=page,
            limit=limit
        )

    @staticmethod
    def get_transaction_by_id(
        db: Session,
        user_id: int,
        transaction_id: int
    ):
        return TransactionService.get_transaction_by_id(
            db=db,
            user_id=user_id,
            transaction_id=transaction_id
        )