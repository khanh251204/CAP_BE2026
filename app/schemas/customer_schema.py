from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.schemas.debt_schema import CustomerBrief, DebtListItem, PaginationMeta


class CustomerCreateRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255, description="Tên khách hàng")
    phone_number: Optional[str] = Field(None, max_length=20, description="Số điện thoại")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    address: Optional[str] = Field(None, max_length=255, description="Địa chỉ")
    customer_type: Optional[str] = Field(None, description="Loại khách hàng (ví dụ: REGULAR, VIP)")


class CustomerUpdateRequest(BaseModel):
    customer_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tên khách hàng")
    phone_number: Optional[str] = Field(None, max_length=20, description="Số điện thoại")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    address: Optional[str] = Field(None, max_length=255, description="Địa chỉ")
    customer_type: Optional[str] = Field(None, description="Loại khách hàng")


class CustomerResponse(BaseModel):
    customer_id: int
    user_id: int
    customer_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    customer_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomerDebtSummary(BaseModel):
    total_original: float
    total_paid: float
    total_remaining: float
    unpaid_count: int
    partial_count: int
    paid_count: int


class CustomerDetailResponse(BaseModel):
    customer_id: int
    customer_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    customer_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    debt_summary: CustomerDebtSummary


class CustomerDebtListResponse(BaseModel):
    customer: CustomerBrief
    debt_summary: CustomerDebtSummary
    debts: List[DebtListItem]


class PaginatedCustomerListResponse(BaseModel):
    items: List[CustomerResponse]
    pagination: PaginationMeta
