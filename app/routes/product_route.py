from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.product_controller import ProductController
from app.configs.jwt import get_current_user_id


router = APIRouter()


# ==========================================
# GET Táº¤T Cáº¢ PRODUCT
# ==========================================

@router.get("/products")
def get_all_products(
    db: Session = Depends(get_db)
):
    return ProductController.get_all_products(db)


# ==========================================
# GET PRODUCT THEO ID
# ==========================================

@router.get("/product/{product_id}")
def get_product_by_id(
    product_id: int,
    db: Session = Depends(get_db)
):
    return ProductController.get_product_by_id(
        product_id,
        db
    )


# ==========================================
# GET PRODUCT THEO USER
# ==========================================

@router.get("/products/user")
def get_products_by_user_id(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.get_products_by_user_id(
        user_id,
        db
    )


# ==========================================
# XÃC NHáº¬N / NHáº¬P TAY PRODUCT
# ==========================================

@router.post("/productsNew")
def create_product(
    data: dict,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.create_product(
        data,
        db
    )


# ==========================================
# Sá»¬A PRODUCT
# ==========================================

@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    return ProductController.update_product(
        product_id,
        data,
        db
    )


# ==========================================
# XÃ“A Má»€M PRODUCT
# ==========================================

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    return ProductController.delete_product(
        product_id,
        db
    )
