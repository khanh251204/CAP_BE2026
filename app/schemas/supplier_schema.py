from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.schemas.debt_schema import SupplierBrief, DebtListItem, PaginationMeta


class SupplierCreateRequest(BaseModel):
    supplier_name: str = Field(..., min_length=1, max_length=255, description="Tên nhà cung cấp")
    phone_number: Optional[str] = Field(None, max_length=20, description="Số điện thoại")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    address: Optional[str] = Field(None, max_length=255, description="Địa chỉ")
    product_group: Optional[str] = Field(None, max_length=100, description="Nhóm hàng cung cấp")
    tax_code: Optional[str] = Field(None, max_length=50, description="Mã số thuế")
    note: Optional[str] = Field(None, description="Ghi chú")


class SupplierUpdateRequest(BaseModel):
    supplier_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tên nhà cung cấp")
    phone_number: Optional[str] = Field(None, max_length=20, description="Số điện thoại")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    address: Optional[str] = Field(None, max_length=255, description="Địa chỉ")
    product_group: Optional[str] = Field(None, max_length=100, description="Nhóm hàng cung cấp")
    tax_code: Optional[str] = Field(None, max_length=50, description="Mã số thuế")
    note: Optional[str] = Field(None, description="Ghi chú")


class SupplierResponse(BaseModel):
    supplier_id: int
    user_id: int
    supplier_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    product_group: Optional[str] = None
    tax_code: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SupplierDebtSummary(BaseModel):
    total_original: float
    total_paid: float
    total_remaining: float
    unpaid_count: int
    partial_count: int
    paid_count: int


class SupplierDetailResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    product_group: Optional[str] = None
    tax_code: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    debt_summary: SupplierDebtSummary


class SupplierDebtListResponse(BaseModel):
    supplier: SupplierBrief
    debt_summary: SupplierDebtSummary
    debts: List[DebtListItem]


class PaginatedSupplierListResponse(BaseModel):
    items: List[SupplierResponse]
    pagination: PaginationMeta
