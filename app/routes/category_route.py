from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers.category_controller import CategoryController
from app.configs.database import get_db


router = APIRouter()


@router.get("/categories")
def category(db: Session = Depends(get_db)):

    return CategoryController.get_all_categories(db)