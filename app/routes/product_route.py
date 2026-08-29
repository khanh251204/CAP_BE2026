from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.product_controller import ProductController
from app.configs.jwt import get_current_user_id


router = APIRouter()

# ==========================================
# GET PRODUCTS WITH STOCK - THEO USER ĐĂNG NHẬP
# ==========================================

@router.get("/inventories")
def get_products_with_stock(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.get_all_products_with_stock(user_id, db)

# ==========================================
# TÌM KIẾM PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.get("/products/search")
def search_products_by_name(
    name: str = Query(..., min_length=1, description="Tên sản phẩm cần tìm"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.search_products_by_name(
        name,
        user_id,
        db
    )


# ==========================================
# GET PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.get("/products")
def get_all_products(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.get_all_products(
        user_id,
        db
    )


# ==========================================
# GET PRODUCT THEO USER ĐĂNG NHẬP
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
# GET PRODUCT THEO ID - THEO USER ĐĂNG NHẬP
# (Lưu ý: Khai báo SAU các route /products/xxx tĩnh)
# ==========================================

@router.get("/product/{product_id}")
def get_product_by_id(
    product_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.get_product_by_id(
        product_id,
        user_id,
        db
    )


# ==========================================
# THÊM PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.post("/productsNew")
def create_product(
    data: dict,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.create_product(
        data,
        user_id,
        db
    )


# ==========================================
# SỬA PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.put("/products/{product_id}")
def update_product(
    product_id: int,
    data: dict,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.update_product(
        product_id,
        data,
        user_id,
        db
    )


# ==========================================
# XÓA PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.delete_product(
        product_id,
        user_id,
        db
    )