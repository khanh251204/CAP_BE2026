from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.debt_controller import DebtController
from app.services.debt_service import DebtService


router = APIRouter()


# ==========================================
# GET TẤT CẢ
# ==========================================

@router.get("/debts")
def get_all_debts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return DebtController.get_all_debts(
        user_id,
        db
    )


# ==========================================
# GET BY ID
# ==========================================

@router.get("/debts/{debt_id}")
def get_debt_by_id(
    debt_id: int,
    db: Session = Depends(get_db)
):

    debt = DebtController.get_debt_by_id(
        debt_id,
        db
    )

    if not debt:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy công nợ"
        )

    return debt


# ==========================================
# GET BY USER
# ==========================================

@router.get("/debts/user/{user_id}")
def get_debts_by_user(
    user_id: int,
    db: Session = Depends(get_db)
):

    return DebtController.get_debts_by_user_id(
        user_id,
        db
    )


# ==========================================
# SEARCH THEO TÊN
# CUSTOMER + SUPPLIER
# ==========================================

@router.get("/debts/search")
def search_debts(
    name: str,
    db: Session = Depends(get_db)
):

    return DebtController.search_debts(
        name,
        db
    )


# ==========================================
# GET CUSTOMER
# ==========================================

@router.get("/debts/customer/{customer_id}")
def get_customer_name(
    customer_id: int,
    db: Session = Depends(get_db)
):

    result = DebtService.get_customer_name(
        customer_id,
        db
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy khách hàng"
        )

    return result


# ==========================================
# GET SUPPLIER
# ==========================================

@router.get("/debts/supplier/{supplier_id}")
def get_supplier_name(
    supplier_id: int,
    db: Session = Depends(get_db)
):

    result = DebtService.get_supplier_name(
        supplier_id,
        db
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy nhà cung cấp"
        )

    return result


# ==========================================
# CREATE
# ==========================================

@router.post("/debts")
def create_debt(
    data: dict,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):

    data["user_id"] = user_id

    return DebtController.create_debt(
        data,
        db
    )


# ==========================================
# UPDATE
# ==========================================

@router.put("/debts/{debt_id}")
def update_debt(
    debt_id: int,
    data: dict,
    db: Session = Depends(get_db)
):

    debt = DebtController.update_debt(
        debt_id,
        data,
        db
    )

    if not debt:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy công nợ"
        )

    return debt


# ==========================================
# DELETE
# ==========================================

@router.delete("/debts/{debt_id}")
def delete_debt(
    debt_id: int,
    db: Session = Depends(get_db)
):

    debt = DebtController.delete_debt(
        debt_id,
        db
    )

    if not debt:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy công nợ"
        )

    return {
        "message": "Xóa công nợ thành công",
        "debt_id": debt_id
    }