from typing import Optional, List
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_permission
from app.controllers.debt_controller import DebtController
from app.schemas.debt_schema import (
    DebtSummaryResponse,
    PaginatedDebtListResponse,
    DebtDetailResponse,
    DebtPaymentHistoryItem,
    PayDebtRequest,
    PayDebtResponse,
)

debt_router = APIRouter(prefix="/debts", tags=["Debt Management"])


@debt_router.get(
    "/summary",
    response_model=DebtSummaryResponse,
    summary="Thống kê tổng quan công nợ Dashboard (receivable & payable)",
    dependencies=[Depends(require_permission("debt:read"))],
)
def get_debt_summary(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.get_summary(user_id=user_id, db=db)


@debt_router.post(
    "/{debt_id}/payments",
    response_model=PayDebtResponse,
    summary="Thanh toán chính xác theo debt_id (Mục 10 & 11)",
    dependencies=[Depends(require_permission("debt:manage"))],
)
def pay_debt_by_id(
    debt_id: int = Path(..., ge=1, description="ID công nợ cần thanh toán"),
    request: PayDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.pay_debt_exact(
        debt_id=debt_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
        user_id=user_id,
        db=db,
    )


@debt_router.get(
    "/{debt_id}/payments",
    response_model=List[DebtPaymentHistoryItem],
    summary="Lịch sử thanh toán của một khoản nợ (Mục 6.4 & Mục 12)",
    dependencies=[Depends(require_permission("debt:read"))],
)
def get_debt_payments(
    debt_id: int = Path(..., ge=1, description="ID công nợ cần xem lịch sử thanh toán"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.get_payment_history(debt_id=debt_id, user_id=user_id, db=db)


@debt_router.get(
    "/{debt_id}",
    response_model=DebtDetailResponse,
    summary="Chi tiết khoản công nợ kèm thông tin đối tác, giao dịch và thanh toán (Mục 6.3)",
    dependencies=[Depends(require_permission("debt:read"))],
)
def get_debt_detail(
    debt_id: int = Path(..., ge=1, description="ID công nợ cần xem chi tiết"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.get_debt_detail(debt_id=debt_id, user_id=user_id, db=db)


@debt_router.get(
    "",
    response_model=PaginatedDebtListResponse,
    summary="Lấy danh sách tất cả công nợ có phân trang và bộ lọc (Mục 6.2)",
    dependencies=[Depends(require_permission("debt:read"))],
)
def get_all_debts(
    direction: Optional[str] = Query(None, description="Lọc theo chiều nợ: RECEIVABLE, PAYABLE"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PARTIAL, PAID"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên khách hàng hoặc nhà cung cấp"),
    customer_id: Optional[int] = Query(None, description="Lọc theo ID khách hàng"),
    supplier_id: Optional[int] = Query(None, description="Lọc theo ID nhà cung cấp"),
    page: int = Query(1, ge=1, description="Số trang (mặc định 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang (mặc định 20, tối đa 100)"),
    name: Optional[str] = Query(None, description="Tương thích ngược: lọc tên đối tác hoặc direction"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    effective_search = search
    effective_direction = direction

    if name:
        if name.upper() in ["RECEIVABLE", "PAYABLE"]:
            effective_direction = name.upper()
        elif not effective_search and name.lower() not in ["customer", "supplier"]:
            effective_search = name

    return DebtController.get_debts_paginated(
        user_id=user_id,
        db=db,
        direction=effective_direction,
        status=status,
        search=effective_search,
        customer_id=customer_id,
        supplier_id=supplier_id,
        page=page,
        limit=limit,
    )


__all__ = ["debt_router"]