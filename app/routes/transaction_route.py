from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.transaction_controller import (
    TransactionController
)
from app.schemas.transaction_schema import TransactionCreateRequest
from app.configs.jwt import get_current_user_id


transaction_router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)


# @transaction_router.get("")
# def get_transactions(
#     page: int = Query(
#         default=1,
#         ge=1
#     ),

#     limit: int = Query(
#         default=10,
#         ge=1,
#         le=100
#     ),

#     db: Session = Depends(get_db)
# ):
#     user_id = 150002

#     return TransactionController.get_transactions(
#         db=db,
#         user_id=user_id,
#         page=page,
#         limit=limit
#     )


# @transaction_router.get("/{transaction_id}")
# def get_transaction_detail(
#     transaction_id: int,

#     db: Session = Depends(get_db)
# ):
#     user_id = 150002

#     return TransactionController.get_transaction_detail(
#         db=db,
#         user_id=user_id,
#         transaction_id=transaction_id
#     )

@transaction_router.post("/")
def save_transaction(
    request: TransactionCreateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        # Tự động gom dữ liệu phẳng từ FE thành cấu trúc Nested cho Service đọc
        groq_result_dict = {
            "transaction_analysis": {
                "text": request.text,
                "intent": request.intent,
                "type": request.type,
                "entities": {
                    "product": request.product,
                    "price": request.price,
                    "quantity": request.quantity,
                    "unit": request.unit,
                    "customer": request.customer,
                    "supplier": request.supplier,
                    "date": request.date,
                    "payment": request.payment
                }
            }
        }
        

        
        # Gọi thẳng xuống Controller
        saved_transaction = TransactionController.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=None,
            groq_result=groq_result_dict
        )
        
        return {
            "success": True,
            "message": "Đã lưu giao dịch thành công!",
            "data": saved_transaction
        }
        
    except ValueError as ve:
        return {"success": False, "message": f"Thiếu thông tin: {str(ve)}"}
    except Exception as e:
        return {"success": False, "message": f"Lưu database thất bại: {str(e)}"}