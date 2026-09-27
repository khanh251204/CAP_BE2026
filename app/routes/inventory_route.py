from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.configs.database import get_db
from app.controllers.inventory_controller import InventoryController
from app.configs.jwt import get_current_user_id  # Thay thế bằng dependency thực tế của dự án bạn
# Thay thế dòng dưới bằng dependency lấy user hiện tại thực tế của dự án bạn
# from app.configs.security import get_current_user 

router = APIRouter()




@router.post("/import", response_model=Dict[str, Any])
def import_goods(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """API Nhập kho hàng hóa"""
    result = InventoryController.import_goods(db=db, user_id=user_id, payload=payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/sell", response_model=Dict[str, Any])
def sell_goods(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """API Bán hàng / Xuất kho"""
    result = InventoryController.sell_goods(db=db, user_id=user_id, payload=payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/check-stock", response_model=Dict[str, Any])
def check_stock(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """API Kiểm tra tồn kho sản phẩm"""
    result = InventoryController.check_stock(db=db, user_id=user_id, payload=payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result