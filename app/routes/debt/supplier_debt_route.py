from typing import Optional, List
from fastapi import APIRouter, Depends, Path, Query, HTTPException
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.debt_controller import DebtController
from app.repositories.debt_repository import DebtRepository
from app.schemas.debt_schema import (
    CreateSupplierDebtRequest,
    CreateSupplierDebtResponse,
    PaySupplierDebtRequest,
    PaySupplierDebtResponse,
    SupplierDebtItemResponse,
    PaySupplierDebtBySupplierResponse,
)

supplier_debt_router = APIRouter()


@supplier_debt_router.post(
    "/supplier",
    response_model=CreateSupplierDebtResponse,
    summary="Tạo công nợ nhà cung cấp (create_supplier_debt / ghi_no_nha_cung_cap)",
)
def create_supplier_debt(
    request: CreateSupplierDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.create_supplier_debt(
        db=db,
        user_id=user_id,
        supplier_id=request.supplier_id,
        total_debt=request.total_debt,
        transaction_id=request.transaction_id,
        note=request.note,
    )


@supplier_debt_router.get(
    "/supplier",
    response_model=List[SupplierDebtItemResponse],
    summary="Lấy danh sách công nợ nhà cung cấp (PAYABLE)",
)
def get_supplier_debts(
    supplier_id: Optional[int] = Query(None, description="Lọc theo ID nhà cung cấp"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PARTIAL, PAID"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên nhà cung cấp"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.get_supplier_debts(
        user_id=user_id,
        db=db,
        supplier_id=supplier_id,
        status=status,
        search=search,
    )


@supplier_debt_router.post(
    "/supplier/payments",
    response_model=PaySupplierDebtResponse,
    summary="Trả tiền nợ nhà cung cấp linh hoạt qua body (Mục 7)",
)
def pay_supplier_debt_by_body(
    request: PaySupplierDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.pay_supplier_debt(
        db=db,
        user_id=user_id,
        debt_id=request.debt_id,
        supplier_id=request.supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@supplier_debt_router.post(
    "/supplier/{id}/payments",
    response_model=PaySupplierDebtResponse,
    summary="Trả tiền nợ nhà cung cấp (đích danh theo debt_id hoặc FIFO theo supplier_id)",
)
def pay_supplier_debt_by_id(
    id: int = Path(..., description="ID công nợ cần trả (nếu nợ cụ thể) hoặc ID nhà cung cấp (nếu trả tổng FIFO)"),
    request: PaySupplierDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    debt_id = request.debt_id
    supplier_id = request.supplier_id

    if not debt_id and not supplier_id:
        debt = DebtRepository.get_debt_by_id_and_user(debt_id=id, user_id=user_id, db=db, direction="PAYABLE")
        if debt:
            debt_id = id
        else:
            supplier = DebtRepository.get_supplier_by_id_and_user(supplier_id=id, user_id=user_id, db=db)
            if supplier:
                supplier_id = id
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Không tìm thấy công nợ hoặc nhà cung cấp với ID {id}"
                )

    return DebtController.pay_supplier_debt(
        db=db,
        user_id=user_id,
        debt_id=debt_id,
        supplier_id=supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@supplier_debt_router.post(
    "/supplier-account/{supplier_id}/payments",
    response_model=PaySupplierDebtBySupplierResponse,
    summary="Trả tiền nợ nhà cung cấp - tự động phân bổ FIFO qua nhiều khoản nợ (Compatibility alias)",
)
def pay_supplier_debt_fifo(
    supplier_id: int = Path(..., description="ID nhà cung cấp cần trả nợ"),
    request: PaySupplierDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.pay_supplier_debt(
        db=db,
        user_id=user_id,
        supplier_id=supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )
