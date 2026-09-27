"""
Admin Dashboard — Pydantic Schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class AdminDashboardPeriod(BaseModel):
    period_type: str = Field(..., description="DAY, MONTH, QUARTER, YEAR, CUSTOM")
    start: str = Field(..., description="Thời gian bắt đầu (ISO 8601 hoặc YYYY-MM-DD)")
    end: str = Field(..., description="Thời gian kết thúc (ISO 8601 hoặc YYYY-MM-DD)")


class AdminDashboardKPISummary(BaseModel):
    revenue: float = Field(0.0, description="Tổng doanh thu bán hàng")
    expense: float = Field(0.0, description="Tổng chi phí hoạt động")
    profit: float = Field(0.0, description="Lợi nhuận ước tính (Revenue - Expense)")
    purchase: float = Field(0.0, description="Tổng chi phí nhập hàng")
    receivable: float = Field(0.0, description="Tổng công nợ phải thu của khách hàng")
    payable: float = Field(0.0, description="Tổng công nợ phải trả cho nhà cung cấp")
    transaction_count: int = Field(0, description="Tổng số lượng giao dịch")
    user_count: int = Field(0, description="Tổng số người dùng hệ thống")
    product_count: int = Field(0, description="Tổng số sản phẩm trong hệ thống")


class AdminDashboardSummaryResponse(BaseModel):
    period: AdminDashboardPeriod = Field(..., description="Thông tin kỳ báo cáo")
    summary: AdminDashboardKPISummary = Field(..., description="Chỉ số KPI tổng quan")


class AdminDashboardTrendItem(BaseModel):
    date: str = Field(..., description="Mốc thời gian (YYYY-MM-DD)")
    revenue: float = Field(0.0, description="Doanh thu")
    expense: float = Field(0.0, description="Chi phí")
    profit: float = Field(0.0, description="Lợi nhuận")
    transaction_count: int = Field(0, description="Số giao dịch")


class AdminDashboardTopProductItem(BaseModel):
    product_id: int = Field(..., description="ID sản phẩm")
    product_name: str = Field(..., description="Tên sản phẩm")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    quantity_sold: float = Field(0.0, description="Số lượng đã bán")
    revenue: float = Field(0.0, description="Doanh thu mang lại")


class AdminDashboardExpenseCategoryItem(BaseModel):
    category_id: Optional[int] = Field(None, description="ID danh mục chi phí")
    category_name: str = Field(..., description="Tên danh mục chi phí")
    amount: float = Field(0.0, description="Tổng chi phí theo danh mục")
