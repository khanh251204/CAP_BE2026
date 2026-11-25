"""
Admin Debt Management — Pydantic Schemas

Response schemas cho Admin quản lý công nợ toàn hệ thống (Nợ phải thu khách hàng / Nợ phải trả NCC):
- Danh sách khoản nợ (phân trang, bộ lọc, tìm kiếm)
- Thống kê KPI công nợ theo bộ lọc
- Chi tiết khoản nợ kèm thông tin User, Đối tác, Giao dịch gốc và Lịch sử thanh toán
"""
from typing import Optional, List
from pydantic import BaseModel, Field

from app.schemas.admin_transaction_schema import (
    AdminUserBrief,
    AdminAccountBrief,
    AdminTransactionDetailItem,
    AdminPagination,
)


class AdminDebtPartnerBrief(BaseModel):
    """Thông tin đối tác (Khách hàng hoặc Nhà cung cấp) trong khoản nợ."""
    id: int
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    partner_type: str = Field(..., description="CUSTOMER hoặc SUPPLIER")
    sub_type: Optional[str] = Field(None, description="customer_type hoặc product_group")
    tax_code: Optional[str] = None
    note: Optional[str] = None


class AdminDebtSourceTransaction(BaseModel):
    """Giao dịch gốc phát sinh khoản nợ."""
    transaction_id: int
    transaction_date: Optional[str] = None
    intent_name: Optional[str] = None
    intent_type: Optional[str] = None
    input_method: Optional[str] = None
    input_text: Optional[str] = None
    note: Optional[str] = None
    total_amount: float = 0.0
    payment_status: Optional[str] = None
    details: List[AdminTransactionDetailItem] = Field(default_factory=list)


class AdminDebtPaymentItem(BaseModel):
    """Một lần thanh toán công nợ (Debt_Payment)."""
    payment_id: int
    debt_id: int
    transaction_id: Optional[int] = None
    account_id: Optional[int] = None
    account: Optional[AdminAccountBrief] = None
    amount: float = 0.0
    payment_percentage: Optional[float] = None
    payment_date: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None


class AdminDebtListItem(BaseModel):
    """Một khoản công nợ trong danh sách Admin."""
    debt_id: int
    transaction_id: Optional[int] = None
    user_id: int
    user: Optional[AdminUserBrief] = None
    direction: str = Field(..., description="RECEIVABLE hoặc PAYABLE")
    status: str = Field(..., description="UNPAID, PARTIAL, hoặc PAID")
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    partner: Optional[AdminDebtPartnerBrief] = None
    original_amount: float = 0.0
    paid_amount: float = 0.0
    remaining_debt: float = 0.0
    payment_count: int = 0
    input_text: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AdminDebtListResponse(BaseModel):
    items: List[AdminDebtListItem]
    pagination: AdminPagination


class AdminDebtSummaryResponse(BaseModel):
    """Thống kê tổng quan công nợ toàn hệ thống theo bộ lọc."""
    total_count: int = Field(0, description="Tổng số khoản nợ khớp bộ lọc")
    unpaid_count: int = Field(0, description="Số khoản chưa thanh toán (UNPAID)")
    partial_count: int = Field(0, description="Số khoản thanh toán 1 phần (PARTIAL)")
    paid_count: int = Field(0, description="Số khoản đã tất toán (PAID)")
    receivable_count: int = Field(0, description="Tổng số khoản nợ phải thu (khách nợ)")
    payable_count: int = Field(0, description="Tổng số khoản nợ phải trả (nợ NCC)")
    receivable_original: float = Field(0.0, description="Tổng nợ gốc phải thu")
    receivable_paid: float = Field(0.0, description="Tổng đã thu từ khách")
    receivable_remaining: float = Field(0.0, description="Số dư nợ phải thu còn lại")
    payable_original: float = Field(0.0, description="Tổng nợ gốc phải trả NCC")
    payable_paid: float = Field(0.0, description="Tổng đã trả cho NCC")
    payable_remaining: float = Field(0.0, description="Số dư nợ phải trả NCC còn lại")
    net_remaining: float = Field(0.0, description="Chênh lệch công nợ còn lại = receivable_remaining - payable_remaining")


class AdminDebtDetailResponse(AdminDebtListItem):
    """Chi tiết khoản công nợ kèm giao dịch gốc và lịch sử thanh toán."""
    transaction: Optional[AdminDebtSourceTransaction] = None
    payments: List[AdminDebtPaymentItem] = Field(default_factory=list)
