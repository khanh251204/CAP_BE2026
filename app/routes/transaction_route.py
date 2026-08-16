from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.transaction_controller import (
    TransactionController
)


transaction_router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)


@transaction_router.get("")
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

    db: Session = Depends(get_db)
):
    user_id = 150002

    return TransactionController.get_transactions(
        db=db,
        user_id=user_id,
        page=page,
        limit=limit
    )


@transaction_router.get("/{transaction_id}")
def get_transaction_detail(
    transaction_id: int,

    db: Session = Depends(get_db)
):
    user_id = 150002

    return TransactionController.get_transaction_detail(
        db=db,
        user_id=user_id,
        transaction_id=transaction_id
    )