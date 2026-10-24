from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime, time
from decimal import Decimal
from app.schemas.report_schema import LiveSummary, TransactionReportItem


class ClosingPeriodRequest(BaseModel):
    period_type: str = Field(..., description="DAY, MONTH, QUARTER, YEAR")
    date: Optional[str] = Field(None, description="YYYY-MM-DD (bắt buộc cho DAY)")
    year: Optional[int] = Field(None, description="Năm (cho MONTH, QUARTER, YEAR)")
    month: Optional[int] = Field(None, description="Tháng 1-12 (cho MONTH)")
    quarter: Optional[int] = Field(None, description="Quý 1-4 (cho QUARTER)")
    note: Optional[str] = None


class ClosingPreviewResponse(BaseModel):
    period_type: str
    period_start: str
    period_end: str
    is_closed: bool = False
    existing_closing_id: Optional[int] = None
    summary: LiveSummary
    transaction_count: int = 0
    total_inventory_value: Decimal = Decimal("0.00")


class ClosingPeriodResponse(BaseModel):
    closing_id: int
    user_id: int
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
    closed_at: str
    created_at: str
    transaction_count: Optional[int] = None
    # Giao dịch thuộc kỳ nhưng phát sinh sau giờ chốt (chưa có trong snapshot)
    late_transaction_count: Optional[int] = 0
    needs_reclose: Optional[bool] = False


class ClosingPeriodListResponse(BaseModel):
    items: List[ClosingPeriodResponse] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class ClosingTransactionsResponse(BaseModel):
    closing_id: int
    items: List[TransactionReportItem] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class ClosingReopenRequest(BaseModel):
    reason: Optional[str] = None


class ClosingSettingResponse(BaseModel):
    setting_id: int
    user_id: int
    period_type: str
    closing_time: str
    auto_close: bool
    send_report: bool
    report_channel: str
    timezone: str
    is_active: bool


class ClosingSettingUpdateRequest(BaseModel):
    period_type: Optional[str] = None
    closing_time: Optional[str] = None  # Format "HH:MM:SS" or "HH:MM"
    auto_close: Optional[bool] = None
    send_report: Optional[bool] = None
    report_channel: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class ClosingReportResponse(BaseModel):
    report_id: int
    closing_id: int
    user_id: int
    report_type: str
    recipient_email: str
    send_status: str
    sent_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str


class ClosingReportListResponse(BaseModel):
    items: List[ClosingReportResponse] = Field(default_factory=list)
    total: int = 0
