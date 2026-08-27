from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.transaction_controller import (
    TransactionController
)
from app.schemas.transaction_schema import TransactionCreateRequest
from app.configs.jwt import get_current_user_id


transaction_router = APIRouter()


@transaction_router.get("/transactions")
def get_transactions(
    page: int = Query(
        default=1,
        ge=1
    ),

    limit: int = Query(
        default=10,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):

    return TransactionController.get_transactions(
        db=db,
        user_id=user_id,
        page=page,
        limit=limit
    )


@transaction_router.get("/transaction/{transaction_id}")
def get_transaction_by_id(
    transaction_id: int,

    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):


    return TransactionController.get_transaction_by_id(
        db=db,
        user_id=user_id,
        transaction_id=transaction_id
    )

@transaction_router.post("/transaction")
def save_transaction(
    request: TransactionCreateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        # Tá»± Ä‘á»™ng gom dá»¯ liá»‡u pháº³ng tá»« FE thÃ nh cáº¥u trÃºc Nested cho Service Ä‘á»c
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



        # Gá»i tháº³ng xuá»‘ng Controller
        saved_transaction = TransactionController.save_groq_transaction(
            db=db,
            user_id=user_id,
            account_id=None,
            groq_result=groq_result_dict
        )

        return {
            "success": True,
            "message": "ÄÃ£ lÆ°u giao dá»‹ch thÃ nh cÃ´ng!",
            "data": saved_transaction
        }

    except ValueError as ve:
        return {"success": False, "message": f"Thiáº¿u thÃ´ng tin: {str(ve)}"}
    except Exception as e:
        return {"success": False, "message": f"LÆ°u database tháº¥t báº¡i: {str(e)}"}
