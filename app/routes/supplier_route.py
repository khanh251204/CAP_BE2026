from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.supplier_controller import SupplierController
from app.configs.jwt import get_current_user_id


router = APIRouter(
)


@router.get("/suppliers")
def get_suppliers(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return SupplierController.get_suppliers(
        db=db,
        user_id=user_id
    )