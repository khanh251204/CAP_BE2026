"""
Admin Closing Management — Pydantic Schemas

Admin xem / quản lý chốt sổ của toàn bộ người dùng.
Không trả password_hash, token hay dữ liệu nhạy cảm của User.
"""
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.closing_schema import ClosingReportResponse, ClosingSettingResponse


class AdminPagination(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class AdminClosingUserBrief(BaseModel):
    """Thông tin chủ sổ an toàn cho Admin xem."""
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    business_type: Optional[str] = None
    store_name: Optional[str] = None


# ========================================
# Overview
# ========================================

class AdminClosingOverviewResponse(BaseModel):
    total_periods: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict, description="CLOSED / OPEN / REOPENED")
    by_period_type: Dict[str, int] = Field(default_factory=dict, description="DAY / MONTH / QUARTER / YEAR")
    users_with_closings: int = 0
    closed_last_7_days: int = 0
    open_periods: int = Field(0, description="Số kỳ đang mở lại, chưa chốt lại")
    reports_by_status: Dict[str, int] = Field(default_factory=dict, description="PENDING / SENT / FAILED")
    settings_total: int = 0
    auto_close_enabled: int = Field(0, description="Số user đang bật tự động chốt sổ")
    settings_inactive: int = 0


# ========================================
# Closing periods
# ========================================

class AdminClosingPeriodItem(BaseModel):
    closing_id: int
    user_id: int
    user: Optional[AdminClosingUserBrief] = None
    period_type: str
    period_start: str
    period_end: str
    total_sales: Decimal
    total_purchase: Decimal
    total_income: Decimal
    total_expense: Decimal
    total_receivable: Decimal
    total_payable: Decimal
    total_inventory_value: Optional[Decimal] = Decimal("0.00")
    status: str
    note: Optional[str] = None
    closed_at: Optional[str] = None
    created_at: Optional[str] = None
    transaction_count: int = 0
    failed_report_count: int = 0


class AdminClosingPeriodListResponse(BaseModel):
    items: List[AdminClosingPeriodItem] = Field(default_factory=list)
    pagination: AdminPagination


class AdminClosingPeriodDetailResponse(AdminClosingPeriodItem):
    reports: List[ClosingReportResponse] = Field(default_factory=list)


class AdminClosingReopenRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Lý do mở lại kỳ chốt (bắt buộc với Admin)")
    notify_user: bool = Field(True, description="Gửi thông báo cho chủ sổ")


class AdminClosingRecloseRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú khi chốt lại kỳ")


# ========================================
# Closing reports (email log)
# ========================================

class AdminClosingReportItem(ClosingReportResponse):
    user: Optional[AdminClosingUserBrief] = None
    period_type: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class AdminClosingReportListResponse(BaseModel):
    items: List[AdminClosingReportItem] = Field(default_factory=list)
    pagination: AdminPagination


# ========================================
# Closing settings
# ========================================

class AdminClosingSettingItem(ClosingSettingResponse):
    user: Optional[AdminClosingUserBrief] = None
    updated_at: Optional[str] = None


class AdminClosingSettingListResponse(BaseModel):
    items: List[AdminClosingSettingItem] = Field(default_factory=list)
    pagination: AdminPagination
