from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.schemas.debt.customer_debt_schema import DebtAllocationItem


class DebtSummaryCategory(BaseModel):
    total_remaining: float
    count: int


class DebtSummaryResponse(BaseModel):
    receivable: DebtSummaryCategory
    payable: DebtSummaryCategory


class CustomerBrief(BaseModel):
    customer_id: int
    customer_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    customer_type: Optional[str] = None


class SupplierBrief(BaseModel):
    supplier_id: int
    supplier_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    product_group: Optional[str] = None
    tax_code: Optional[str] = None
    note: Optional[str] = None


class TransactionDetailItemResponse(BaseModel):
    detail_id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: float
    unit: Optional[str] = None
    unit_price: float
    subtotal: float


class DebtTransactionResponse(BaseModel):
    transaction_id: int
    transaction_date: Optional[datetime] = None
    intent_name: Optional[str] = None
    intent_type: Optional[str] = None
    type: Optional[str] = None
    input_text: Optional[str] = None
    total_amount: Optional[float] = None
    payment_status: Optional[str] = None
    details: List[TransactionDetailItemResponse] = Field(default_factory=list)


class DebtPaymentAccountBrief(BaseModel):
    account_id: int
    account_name: Optional[str] = None
    account_type: Optional[str] = None


class DebtInfo(BaseModel):
    original_amount: float
    paid_amount: float
    remaining_debt: float
    status: str


class DebtListItem(BaseModel):
    debt_id: int
    transaction_id: Optional[int] = None
    direction: str
    customer: Optional[CustomerBrief] = None
    supplier: Optional[SupplierBrief] = None
    original_amount: float
    paid_amount: float
    remaining_debt: float
    status: str
    transaction: Optional[DebtTransactionResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Tương thích ngược
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedDebtListResponse(BaseModel):
    items: List[DebtListItem]
    pagination: PaginationMeta


class DebtPaymentHistoryItem(BaseModel):
    payment_id: int
    debt_id: int
    transaction_id: Optional[int] = None
    account_id: Optional[int] = None
    account: Optional[DebtPaymentAccountBrief] = None
    amount: float
    payment_percentage: Optional[float] = None
    payment_date: Optional[datetime] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class DebtDetailResponse(BaseModel):
    debt_id: int
    direction: str
    customer: Optional[CustomerBrief] = None
    supplier: Optional[SupplierBrief] = None
    debt: Optional[DebtInfo] = None
    transaction: Optional[DebtTransactionResponse] = None
    payments: List[DebtPaymentHistoryItem] = Field(default_factory=list)

    # Tương thích ngược
    original_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    remaining_debt: Optional[float] = None
    status: Optional[str] = None
    transaction_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PayDebtRequest(BaseModel):
    account_id: int = Field(..., description="ID tài khoản nguồn/nhận tiền")
    amount: float = Field(..., description="Số tiền thanh toán")
    payment_date: Optional[datetime] = Field(None, description="Thời gian thanh toán (mặc định now)")
    note: Optional[str] = Field(None, description="Ghi chú thanh toán")


class PayDebtAccountResult(BaseModel):
    account_id: int
    account_name: Optional[str] = None
    balance: float


class PayDebtResponse(BaseModel):
    payment_id: int
    debt_id: int
    transaction_id: int
    amount_paid: float
    debt: DebtInfo
    account: PayDebtAccountResult


class FIFODebtPaymentRequest(BaseModel):
    account_id: int = Field(..., description="ID tài khoản thanh toán")
    amount: float = Field(..., description="Số tiền thanh toán")
    payment_date: Optional[datetime] = Field(None, description="Thời gian thanh toán (mặc định now)")
    note: Optional[str] = Field(None, description="Ghi chú thanh toán")


class FIFOAllocationItem(BaseModel):
    debt_id: int
    transaction_id: Optional[int] = None
    amount_applied: float
    remaining_debt: float
    status: str


class FIFOBeforeAfter(BaseModel):
    total_remaining: float


class CustomerFIFOPaymentResponse(BaseModel):
    customer_id: int
    amount_paid: float
    before: FIFOBeforeAfter
    after: FIFOBeforeAfter
    allocations: List[FIFOAllocationItem]


class SupplierFIFOPaymentResponse(BaseModel):
    supplier_id: int
    amount_paid: float
    before: FIFOBeforeAfter
    after: FIFOBeforeAfter
    allocations: List[FIFOAllocationItem]
