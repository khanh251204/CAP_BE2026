"""
Admin Transaction Management — Pydantic Schemas

Response schemas cho Admin xem/tìm kiếm giao dịch.
Reuse các sub-schema từ transaction_schema.py khi có thể.
Không trả password_hash, token, OTP hay dữ liệu nhạy cảm của User.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ========================================
# Sub-schemas cho nested objects
# ========================================

class AdminUserBrief(BaseModel):
    """Thông tin User an toàn cho Admin xem — KHÔNG chứa password/secret."""
    user_id: int
    full_name: str
    email: str
    phone_number: Optional[str] = None
    business_type: Optional[str] = None
    store_name: Optional[str] = None
    role: Optional[str] = None


class AdminProductBrief(BaseModel):
    """Thông tin Product tóm tắt trong Transaction Detail."""
    product_id: int
    product_name: Optional[str] = None
    product_type: Optional[str] = None
    default_unit: Optional[str] = None
    image: Optional[str] = None


class AdminTransactionDetailItem(BaseModel):
    """Chi tiết dòng hàng (Transaction_Detail) theo ERD."""
    detail_id: int
    product_id: int
    quantity: float
    unit: str
    unit_price: float
    subtotal: float
    product: Optional[AdminProductBrief] = None


class AdminAccountBrief(BaseModel):
    account_id: int
    account_name: Optional[str] = None
    account_type: Optional[str] = None


class AdminPartnerBrief(BaseModel):
    """Customer hoặc Supplier tóm tắt."""
    id: Optional[int] = None
    name: Optional[str] = None
    phone_number: Optional[str] = None


class AdminCategoryBrief(BaseModel):
    category_id: int
    category_name: Optional[str] = None
    category_type: Optional[str] = None


# ========================================
# Transaction List Item (Admin view)
# ========================================

class AdminTransactionListItem(BaseModel):
    """Một giao dịch trong danh sách — bao gồm thông tin User."""
    transaction_id: int
    user_id: int
    user: Optional[AdminUserBrief] = None
    intent_id: Optional[int] = None
    intent_name: Optional[str] = None
    intent_type: Optional[str] = None
    category_id: Optional[int] = None
    category: Optional[AdminCategoryBrief] = None
    account_id: Optional[int] = None
    account: Optional[AdminAccountBrief] = None
    customer_id: Optional[int] = None
    customer: Optional[AdminPartnerBrief] = None
    supplier_id: Optional[int] = None
    supplier: Optional[AdminPartnerBrief] = None
    total_amount: float
    payment_status: Optional[str] = None
    input_method: Optional[str] = None
    input_text: Optional[str] = None
    note: Optional[str] = None
    transaction_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    detail_count: int = Field(0, description="Số lượng dòng chi tiết")


# ========================================
# Pagination
# ========================================

class AdminPagination(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


# ========================================
# List Response
# ========================================

class AdminTransactionListResponse(BaseModel):
    items: List[AdminTransactionListItem]
    pagination: AdminPagination


# ========================================
# Detail Response (bao gồm details + user đầy đủ)
# ========================================

class AdminTransactionDetailResponse(BaseModel):
    """Chi tiết đầy đủ một giao dịch cho Admin."""
    transaction_id: int
    user_id: int
    user: Optional[AdminUserBrief] = None
    intent_id: Optional[int] = None
    intent_name: Optional[str] = None
    intent_type: Optional[str] = None
    category_id: Optional[int] = None
    category: Optional[AdminCategoryBrief] = None
    account_id: Optional[int] = None
    account: Optional[AdminAccountBrief] = None
    customer_id: Optional[int] = None
    customer: Optional[AdminPartnerBrief] = None
    supplier_id: Optional[int] = None
    supplier: Optional[AdminPartnerBrief] = None
    total_amount: float
    payment_status: Optional[str] = None
    input_method: Optional[str] = None
    input_text: Optional[str] = None
    note: Optional[str] = None
    transaction_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    details: List[AdminTransactionDetailItem] = Field(default_factory=list)
