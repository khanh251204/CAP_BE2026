from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.schemas.debt.customer_debt_schema import DebtAllocationItem


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
