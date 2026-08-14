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

    return TransactionController.get_transactions(
        db=db,
        page=page,
        limit=limit
    )


@transaction_router.get("/{transaction_id}")
def get_transaction_detail(
    transaction_id: int,

    db: Session = Depends(get_db)
):

    return TransactionController.get_transaction_detail(
        db=db,
        transaction_id=transaction_id
    )