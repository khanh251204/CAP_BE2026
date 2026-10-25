from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.configs.database import get_db
from app.controllers.inventory_controller import InventoryController
from app.configs.jwt import get_current_user_id, require_permission
from app.schemas.inventory_schema import (
    InventoryImportRequest,
    InventorySellRequest,
    InventoryCheckStockRequest,
)

router = APIRouter()


@router.post("/purchases", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("transaction:purchase"))])
def import_goods(
    payload: InventoryImportRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Tạo đơn mua hàng / nhập hàng từ nhà cung cấp (tăng tồn kho)"""
    result = InventoryController.import_goods(db=db, user_id=user_id, payload=payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/sales", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("transaction:create"))])
def sell_goods(
    payload: InventorySellRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Tạo đơn bán hàng (trừ tồn kho theo business rule)"""
    result = InventoryController.sell_goods(db=db, user_id=user_id, payload=payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.get("/inventory/stock", response_model=Dict[str, Any], dependencies=[Depends(require_permission("inventory:read"))])
def check_stock(
    product_id: Optional[int] = Query(None, description="ID sản phẩm cần kiểm tra"),
    product_name: Optional[str] = Query(None, description="Tên sản phẩm cần kiểm tra"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Xem tồn kho hiện tại của một sản phẩm (theo ID hoặc tên)"""
    payload = InventoryCheckStockRequest(product_id=product_id, product_name=product_name)
    result = InventoryController.check_stock(db=db, user_id=user_id, payload=payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result