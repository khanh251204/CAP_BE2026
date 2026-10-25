from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.controllers.product_controller import ProductController
from app.configs.jwt import get_current_user_id, require_permission


router = APIRouter()

# ==========================================
# GET PRODUCTS WITH STOCK - THEO USER ĐĂNG NHẬP
# ==========================================

@router.get("/inventories", dependencies=[Depends(require_permission("inventory:read"))])
def get_products_with_stock(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.get_all_products_with_stock(user_id, db)


# ==========================================
# CẢNH BÁO TỒN KHO: HẾT HÀNG HOẶC DƯỚI MIN_QUANTITY
# ==========================================

@router.get("/products/alerts", dependencies=[Depends(require_permission("inventory:read"))])
@router.get("/products/low-stock", include_in_schema=False, dependencies=[Depends(require_permission("inventory:read"))])
@router.get("/inventories/alerts", include_in_schema=False, dependencies=[Depends(require_permission("inventory:read"))])
def get_stock_alerts(
    type: Optional[str] = Query("ALL", description="Loại cảnh báo: ALL, OUT_OF_STOCK, LOW_STOCK"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách các mặt hàng:
    - Hết hàng (stock <= 0): OUT_OF_STOCK
    - Dưới hoặc bằng định mức tối thiểu (0 < stock <= min_quantity): LOW_STOCK
    """
    return ProductController.get_stock_alerts(
        user_id=user_id,
        db=db,
        alert_type=type
    )


# ==========================================
# TÌM KIẾM PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.get("/products/search", dependencies=[Depends(require_permission("product:read"))])
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

@router.get("/products", dependencies=[Depends(require_permission("product:read"))])
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

@router.get("/products/user", dependencies=[Depends(require_permission("product:read"))])
def get_products_by_user_id(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.get_products_by_user_id(
        user_id,
        db
    )


from app.schemas.product_schema import (
    ProductCreateRequest,
    ProductUpdateRequest,
    InventoryCheckRequest,
    ManualInventoryTransactionRequest,
)


# ==========================================
# THÊM PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.post("/products", status_code=status.HTTP_200_OK, dependencies=[Depends(require_permission("product:create"))])
@router.post("/productsNew", status_code=status.HTTP_200_OK, include_in_schema=False, dependencies=[Depends(require_permission("product:create"))])
def create_product(
    data: ProductCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.create_product(
        data,
        user_id,
        db
    )


# ==========================================
# GET PRODUCT THEO ID - THEO USER ĐĂNG NHẬP
# ==========================================

@router.get("/products/{product_id}", dependencies=[Depends(require_permission("product:read"))])
@router.get("/product/{product_id}", include_in_schema=False, dependencies=[Depends(require_permission("product:read"))])
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
# SỬA PRODUCT - THEO USER ĐĂNG NHẬP
# ==========================================

@router.put("/products/{product_id}", dependencies=[Depends(require_permission("product:update"))])
@router.put("/product/{product_id}", include_in_schema=False, dependencies=[Depends(require_permission("product:update"))])
def update_product(
    product_id: int,
    data: ProductUpdateRequest,
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

@router.delete("/products/{product_id}", dependencies=[Depends(require_permission("product:delete"))])
@router.delete("/product/{product_id}", include_in_schema=False, dependencies=[Depends(require_permission("product:delete"))])
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


# ==========================================
# 1. API KIỂM KÊ TỒN KHO (INVENTORY CHECK / ADJUSTMENT)
# ==========================================

@router.post("/products/{product_id}/inventory-check", dependencies=[Depends(require_permission("inventory:manage"))])
@router.post("/product/{product_id}/inventory-check", include_in_schema=False, dependencies=[Depends(require_permission("inventory:manage"))])
def inventory_check(
    product_id: int,
    data: InventoryCheckRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    API Kiểm kê tồn kho:
    Nhập số lượng đếm thực tế, hệ thống tự tính chênh lệch và cập nhật số dư kho.
    """
    return ProductController.inventory_check(
        product_id=product_id,
        data=data,
        user_id=user_id,
        db=db
    )


# ==========================================
# API PHỤ: NHẬP KHO / XUẤT KHO THỦ CÔNG
# ==========================================

@router.post("/products/{product_id}/inventory-transactions", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("inventory:manage"))])
@router.post("/product/{product_id}/inventory-transactions", status_code=status.HTTP_201_CREATED, include_in_schema=False, dependencies=[Depends(require_permission("inventory:manage"))])
def manual_inventory_transaction(
    product_id: int,
    data: ManualInventoryTransactionRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    API Nhập kho / Xuất kho thủ công (không qua mua bán giao dịch).
    Nếu inventory_type = 'OUT' mà quantity > current_stock -> reject 409 Conflict.
    """
    return ProductController.manual_inventory_transaction(
        product_id=product_id,
        data=data,
        user_id=user_id,
        db=db
    )


# ==========================================
# 3. API LỊCH SỬ TỒN KHO (INVENTORY HISTORY)
# ==========================================

@router.get("/products/{product_id}/inventory-history", dependencies=[Depends(require_permission("inventory:read"))])
@router.get("/product/{product_id}/inventory-history", dependencies=[Depends(require_permission("inventory:read"))])
def get_inventory_history(
    product_id: int,
    from_date: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD)"),
    type: Optional[str] = Query(None, description="Loại biến động: IN, OUT, DAMAGE, ADJUSTMENT"),
    page: int = Query(1, ge=1, description="Trang số"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Lấy lịch sử biến động kho của sản phẩm (sắp xếp created_at DESC).
    """
    parsed_from = None
    if from_date:
        try:
            parsed_from = datetime.fromisoformat(from_date)
        except Exception:
            pass

    parsed_to = None
    if to_date:
        try:
            parsed_to = datetime.fromisoformat(to_date)
        except Exception:
            pass

    types_list = None
    if type:
        types_list = [t.strip().upper() for t in type.split(",") if t.strip()]

    return ProductController.get_inventory_history(
        product_id=product_id,
        user_id=user_id,
        from_date=parsed_from,
        to_date=parsed_to,
        types=types_list,
        page=page,
        limit=limit,
        db=db
    )