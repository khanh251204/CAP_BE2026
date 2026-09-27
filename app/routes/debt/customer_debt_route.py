from typing import Optional, List
from fastapi import APIRouter, Depends, Path, Query, HTTPException
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.debt_controller import DebtController
from app.repositories.debt_repository import DebtRepository
from app.schemas.debt_schema import (
    CreateCustomerDebtRequest,
    CreateCustomerDebtResponse,
    CollectCustomerDebtRequest,
    CollectCustomerDebtResponse,
    CustomerDebtItemResponse,
    CollectCustomerDebtByCustomerResponse,
)

customer_debt_router = APIRouter()


@customer_debt_router.post(
    "/customer",
    response_model=CreateCustomerDebtResponse,
    summary="Tạo công nợ khách hàng (create_customer_debt / ghi_no_khach_hang)",
)
def create_customer_debt(
    request: CreateCustomerDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.create_customer_debt(
        db=db,
        user_id=user_id,
        customer_id=request.customer_id,
        total_debt=request.total_debt,
        transaction_id=request.transaction_id,
        note=request.note,
    )


@customer_debt_router.get(
    "/customer",
    response_model=List[CustomerDebtItemResponse],
    summary="Lấy danh sách công nợ khách hàng (RECEIVABLE)",
)
def get_customer_debts(
    customer_id: Optional[int] = Query(None, description="Lọc theo ID khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PARTIAL, PAID"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên khách hàng"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.get_customer_debts(
        user_id=user_id,
        db=db,
        customer_id=customer_id,
        status=status,
        search=search,
    )


@customer_debt_router.post(
    "/customer/payments",
    response_model=CollectCustomerDebtResponse,
    summary="Thu tiền nợ khách hàng linh hoạt qua body (Mục 7)",
)
def collect_customer_debt_by_body(
    request: CollectCustomerDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        debt_id=request.debt_id,
        customer_id=request.customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@customer_debt_router.post(
    "/customer/{id}/payments",
    response_model=CollectCustomerDebtResponse,
    summary="Thu tiền nợ khách hàng (đích danh theo debt_id hoặc FIFO theo customer_id)",
)
def collect_customer_debt_by_id(
    id: int = Path(..., description="ID công nợ cần thu (nếu nợ cụ thể) hoặc ID khách hàng (nếu thu tổng FIFO)"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    debt_id = request.debt_id
    customer_id = request.customer_id

    if not debt_id and not customer_id:
        debt = DebtRepository.get_debt_by_id_and_user(debt_id=id, user_id=user_id, db=db, direction="RECEIVABLE")
        if debt:
            debt_id = id
        else:
            customer = DebtRepository.get_customer_by_id_and_user(customer_id=id, user_id=user_id, db=db)
            if customer:
                customer_id = id
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Không tìm thấy công nợ hoặc khách hàng với ID {id}"
                )

    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        debt_id=debt_id,
        customer_id=customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@customer_debt_router.post(
    "/customer-account/{customer_id}/payments",
    response_model=CollectCustomerDebtByCustomerResponse,
    summary="Thu tiền nợ khách hàng - tự động phân bổ FIFO qua nhiều khoản nợ (Compatibility alias)",
)
def collect_customer_debt_fifo(
    customer_id: int = Path(..., description="ID khách hàng cần thu nợ"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        customer_id=customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )
