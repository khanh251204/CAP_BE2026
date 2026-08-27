from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.account_controller import AccountController
from app.configs.jwt import get_current_user_id


router = APIRouter()


@router.get("/accounts")
def get_accounts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return AccountController.get_accounts(
        db=db,
        user_id=user_id
    )