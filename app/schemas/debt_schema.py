from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateCustomerDebtRequest(BaseModel):
    """
    POST /debts/customer
    intent: create_customer_debt (ghi_no_khach_hang)
    """
    customer_id: int = Field(..., description="ID khách hàng")
    total_debt: float = Field(..., gt=0, description="Số tiền nợ gốc")
    transaction_id: Optional[int] = Field(
        None,
        description=(
            "Nếu đã có Transaction từ ban_hang; "
            "nếu không truyền, server tự tạo Transaction loại ghi nợ"
        )
    )
    note: Optional[str] = Field(None, description="Ghi chú công nợ")


class CreateCustomerDebtResponse(BaseModel):
    debt_id: int
    status: str
    total_debt: float
    original_amount: float
    remaining_debt: float


class DebtAllocationItem(BaseModel):
    debt_id: int
    payment_id: Optional[int] = None
    amount_applied: float
    remaining_debt: float
    debt_status: str


class CollectCustomerDebtRequest(BaseModel):
    """
    POST /debts/customer/{debt_id}/payments hoặc POST /debts/customer/payments
    intent: collect_customer_debt (thu_no_khach_hang)
    """
    account_id: int = Field(..., description="Tài khoản nhận tiền")
    amount: float = Field(..., description="Số tiền thu")
    debt_id: Optional[int] = Field(None, description="ID công nợ cụ thể cần thu (nếu có)")
    customer_id: Optional[int] = Field(None, description="ID khách hàng (nếu thu tổng, tự phân bổ FIFO)")
    payment_date: Optional[datetime] = Field(
        None,
        description="Mặc định = now nếu không truyền"
    )
    note: Optional[str] = Field(None, description="Ghi chú phiếu thu")


class CollectCustomerDebtResponse(BaseModel):
    amount_collected: float
    payment_id: Optional[int] = None

    # Khi thu đích danh 1 debt_id
    debt_id: Optional[int] = None
    remaining_debt: Optional[float] = None
    debt_status: Optional[str] = None

    # Khi thu theo customer_id (phân bổ FIFO)
    customer_id: Optional[int] = None
    total_remaining_before: Optional[float] = None
    total_remaining_after: Optional[float] = None
    debts: Optional[List[DebtAllocationItem]] = None


class CollectCustomerDebtByCustomerResponse(BaseModel):
    customer_id: int
    amount_collected: float
    payment_id: Optional[int] = None
    total_remaining_before: float
    total_remaining_after: float
    remaining_debt: float
    debt_status: str
    debts: List[DebtAllocationItem]


class CustomerDebtItemResponse(BaseModel):
    debt_id: int
    transaction_id: Optional[int] = None
    user_id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    direction: str
    original_amount: float
    remaining_debt: float
    total_debt: float
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomerDebtListResponse(BaseModel):
    data: List[CustomerDebtItemResponse]
    total: int


# ==========================================
# CÔNG NỢ NHÀ CUNG CẤP (PAYABLE)
# ==========================================
class CreateSupplierDebtRequest(BaseModel):
    """
    POST /debts/supplier
    intent: create_supplier_debt (ghi_no_nha_cung_cap)
    """
    supplier_id: int = Field(..., description="ID nhà cung cấp")
    total_debt: float = Field(..., gt=0, description="Số tiền nợ gốc")
    transaction_id: Optional[int] = Field(
        None,
        description=(
            "Nếu đã có Transaction từ nhap_hang; "
            "nếu không truyền, server tự tạo Transaction loại ghi nợ"
        )
    )
    note: Optional[str] = Field(None, description="Ghi chú công nợ")


class CreateSupplierDebtResponse(BaseModel):
    debt_id: int
    status: str
    total_debt: float
    original_amount: float
    remaining_debt: float


class PaySupplierDebtRequest(BaseModel):
    """
    POST /debts/supplier/{debt_id}/payments hoặc POST /debts/supplier/payments
    intent: pay_supplier_debt (thu_no_nha_cung_cap / tra_no_nha_cung_cap)
    """
    account_id: int = Field(..., description="Tài khoản nguồn trích tiền trả")
    amount: float = Field(..., description="Số tiền trả")
    debt_id: Optional[int] = Field(None, description="ID công nợ cụ thể cần trả (nếu có)")
    supplier_id: Optional[int] = Field(None, description="ID nhà cung cấp (nếu trả tổng, tự phân bổ FIFO)")
    payment_date: Optional[datetime] = Field(
        None,
        description="Mặc định = now nếu không truyền"
    )
    note: Optional[str] = Field(None, description="Ghi chú phiếu chi trả nợ")


class PaySupplierDebtResponse(BaseModel):
    amount_paid: float
    payment_id: Optional[int] = None

    # Khi trả đích danh 1 debt_id
    debt_id: Optional[int] = None
    remaining_debt: Optional[float] = None
    debt_status: Optional[str] = None

    # Khi trả theo supplier_id (phân bổ FIFO)
    supplier_id: Optional[int] = None
    total_remaining_before: Optional[float] = None
    total_remaining_after: Optional[float] = None
    debts: Optional[List[DebtAllocationItem]] = None


class PaySupplierDebtBySupplierResponse(BaseModel):
    supplier_id: int
    amount_paid: float
    payment_id: Optional[int] = None
    total_remaining_before: float
    total_remaining_after: float
    remaining_debt: float
    debt_status: str
    debts: List[DebtAllocationItem]


class SupplierDebtItemResponse(BaseModel):
    debt_id: int
    transaction_id: Optional[int] = None
    user_id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    direction: str
    original_amount: float
    remaining_debt: float
    total_debt: float
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SupplierDebtListResponse(BaseModel):
    data: List[SupplierDebtItemResponse]
    total: int


# ==========================================
# DASHBOARD SUMMARY (Mục 6.1 & Mục 7)
# ==========================================
class DebtSummaryCategory(BaseModel):
    total_remaining: float
    count: int


class DebtSummaryResponse(BaseModel):
    receivable: DebtSummaryCategory
    payable: DebtSummaryCategory


# ==========================================
# CHI TIẾT ĐỐI TÁC, GIAO DỊCH, SẢN PHẨM & TÀI KHOẢN (Mục 8 & 9)
# ==========================================
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


# ==========================================
# LIST ALL DEBTS VỚI PHÂN TRANG (Mục 8)
# ==========================================
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


# ==========================================
# PAYMENT HISTORY & DEBT DETAIL (Mục 9 & Mục 12)
# ==========================================
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


# ==========================================
# THANH TOÁN THEO DEBT_ID (Mục 10 & 11)
# ==========================================
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


# ==========================================
# FIFO DEBT PAYMENT (Mục 13 & 14)
# ==========================================
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
