from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.customer_controller import CustomerController
from app.configs.jwt import get_current_user_id


router = APIRouter(
)


@router.get("/customers")
def get_customers(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return CustomerController.get_customers(
        db=db,
        user_id=user_id
    )