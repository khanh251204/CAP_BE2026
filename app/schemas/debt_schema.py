from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreateCustomerDebtRequest(BaseModel):
    """
    POST /debts/customer
    intent: create_customer_debt
    """
    customer_id: int = Field(..., description="ID khách hàng")
    total_debt: float = Field(..., gt=0, description="Số tiền nợ")
    transaction_id: Optional[int] = Field(
        None,
        description=(
            "Nếu đã có Transaction từ ban_hang; "
            "nếu không truyền, server tự tạo Transaction rỗng loại 'ghi nợ'"
        )
    )
    note: Optional[str] = None


class CreateCustomerDebtResponse(BaseModel):
    debt_id: int
    status: str
    total_debt: float


class CollectCustomerDebtRequest(BaseModel):
    """
    POST /debts/customer/{debt_id}/payments
    intent: collect_customer_debt
    """
    account_id: int = Field(..., description="Tài khoản nhận tiền")
    amount: float = Field(..., gt=0, description="Số tiền thu")
    payment_date: Optional[datetime] = Field(
        None,
        description="Mặc định = now nếu không truyền"
    )
    note: Optional[str] = None


class CollectCustomerDebtResponse(BaseModel):
    payment_id: int
    debt_id: int
    remaining_debt: float
    debt_status: str
