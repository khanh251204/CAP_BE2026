from typing import Optional
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.services.customer_service import CustomerService
from app.services.debt_service import DebtService
from app.schemas.customer_schema import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerResponse,
    CustomerDetailResponse,
    CustomerDebtListResponse,
    PaginatedCustomerListResponse,
)
from app.schemas.debt_schema import (
    FIFODebtPaymentRequest,
    CustomerFIFOPaymentResponse,
)

customer_router = APIRouter(prefix="/customers", tags=["Customer Management"])


@customer_router.post(
    "",
    response_model=CustomerResponse,
    summary="Tạo mới khách hàng (Mục 15)",
)
def create_customer(
    request: CustomerCreateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return CustomerService.create_customer(user_id=user_id, request=request, db=db)


@customer_router.get(
    "",
    response_model=PaginatedCustomerListResponse,
    summary="Lấy danh sách khách hàng (Mục 15)",
)
def get_customers(
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên hoặc số điện thoại"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi mỗi trang"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return CustomerService.get_customers(
        user_id=user_id,
        db=db,
        search=search,
        page=page,
        limit=limit,
    )


@customer_router.get(
    "/{customer_id}",
    response_model=CustomerDetailResponse,
    summary="Chi tiết khách hàng kèm tổng quan công nợ (Mục 16)",
)
def get_customer_detail(
    customer_id: int = Path(..., ge=1, description="ID khách hàng"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return CustomerService.get_customer_detail(
        customer_id=customer_id,
        user_id=user_id,
        db=db,
    )


@customer_router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Cập nhật thông tin khách hàng (PATCH - Mục 15)",
)
@customer_router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Cập nhật thông tin khách hàng (PUT)",
)
def update_customer(
    customer_id: int = Path(..., ge=1, description="ID khách hàng"),
    request: CustomerUpdateRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return CustomerService.update_customer(
        customer_id=customer_id,
        user_id=user_id,
        request=request,
        db=db,
    )


@customer_router.delete(
    "/{customer_id}",
    summary="Xóa khách hàng (Mục 15)",
)
def delete_customer(
    customer_id: int = Path(..., ge=1, description="ID khách hàng"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return CustomerService.delete_customer(
        customer_id=customer_id,
        user_id=user_id,
        db=db,
    )


@customer_router.get(
    "/{customer_id}/debts",
    response_model=CustomerDebtListResponse,
    summary="Danh sách công nợ chi tiết của khách hàng kèm sản phẩm (Mục 17)",
)
def get_customer_debts(
    customer_id: int = Path(..., ge=1, description="ID khách hàng"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return CustomerService.get_customer_debts(
        customer_id=customer_id,
        user_id=user_id,
        db=db,
    )


@customer_router.post(
    "/{customer_id}/debt-payments",
    response_model=CustomerFIFOPaymentResponse,
    summary="Thanh toán tổng công nợ khách hàng theo thuật toán FIFO (Mục 13)",
)
def pay_customer_debt_fifo(
    customer_id: int = Path(..., ge=1, description="ID khách hàng"),
    request: FIFODebtPaymentRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtService.pay_customer_debts_fifo(
        customer_id=customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
        user_id=user_id,
        db=db,
    )
