from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.debt_controller import DebtController
from app.schemas.debt_schema import (
    CreateCustomerDebtRequest,
    CreateCustomerDebtResponse,
    CollectCustomerDebtRequest,
    CollectCustomerDebtResponse,
)

debt_router = APIRouter(prefix="/debts", tags=["Debt — Customer"])


@debt_router.post(
    "/customer",
    response_model=CreateCustomerDebtResponse,
    summary="Tạo công nợ khách hàng (create_customer_debt)",
)
def create_customer_debt(
    request: CreateCustomerDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `create_customer_debt`

    - Nhận `customer_id` + `total_debt`.
    - Nếu `transaction_id` không được truyền, server tự tạo Transaction rỗng loại
      *ghi nợ* (đáp ứng ràng buộc FK bắt buộc trong ERD).
    - Trả về `{ debt_id, status, total_debt }`.
    """
    return DebtController.create_customer_debt(
        db=db,
        user_id=user_id,
        customer_id=request.customer_id,
        total_debt=request.total_debt,
        transaction_id=request.transaction_id,
        note=request.note,
    )


@debt_router.post(
    "/customer/{debt_id}/payments",
    response_model=CollectCustomerDebtResponse,
    summary="Thu tiền nợ khách hàng (collect_customer_debt)",
)
def collect_customer_debt(
    debt_id: int = Path(..., description="ID công nợ cần thu"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `collect_customer_debt`

    Chạy trong **1 DB transaction**:
    1. Insert `Transaction` (intent = collect_customer_debt)
    2. Insert `Debt_Payment`
    3. `UPDATE Account SET balance = balance + amount`
    4. Tính lại tổng đã thu → `UPDATE Debt.status` (open → partial → paid)

    **Validate**: `amount <= remaining_debt`, trả 400 nếu vượt.
    """
    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        debt_id=debt_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )
