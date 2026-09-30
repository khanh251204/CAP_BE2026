"""
Admin Dashboard — Pydantic Schemas

Định nghĩa schema dữ liệu cho Admin Dashboard giám sát hệ sinh thái VoiceCash:
- System KPIs (người dùng, giao dịch, xử lý giọng nói)
- Voice AI Processing & Voice Processing Trend
- User & Transaction Activity & Activity Trend
- Dataset / Data Lake Summary
- Recent System Activity
- System Health
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AdminDashboardPeriod(BaseModel):
    period_type: str = Field(..., description="Loại kỳ: DAY, WEEK, MONTH, QUARTER, YEAR, CUSTOM")
    start: str = Field(..., description="Thời gian bắt đầu (ISO 8601 hoặc YYYY-MM-DD)")
    end: str = Field(..., description="Thời gian kết thúc (ISO 8601 hoặc YYYY-MM-DD)")


class AdminSystemSummary(BaseModel):
    total_users: int = Field(0, description="Tổng số người dùng toàn hệ thống")
    active_users: Optional[int] = Field(None, description="Số người dùng đang hoạt động (đã xác thực, không bị khóa)")
    total_transactions: int = Field(0, description="Tổng số giao dịch đã phát sinh")
    total_voice_processing: int = Field(0, description="Tổng số lượt xử lý giọng nói")
    successful_voice_processing: int = Field(0, description="Số lượt xử lý giọng nói thành công")
    failed_voice_processing: int = Field(0, description="Số lượt xử lý giọng nói thất bại")
    pending_review_voice_processing: int = Field(0, description="Số lượt giọng nói đang chờ duyệt/xử lý")


class AdminVoiceProcessingSummary(BaseModel):
    total: int = Field(0, description="Tổng số lượt xử lý giọng nói trong kỳ")
    success: int = Field(0, description="Số lượt thành công trong kỳ")
    failed: int = Field(0, description="Số lượt thất bại trong kỳ")
    pending_review: int = Field(0, description="Số lượt chờ duyệt/xử lý trong kỳ")


class AdminVoiceProcessingTrendItem(BaseModel):
    date: str = Field(..., description="Ngày (YYYY-MM-DD)")
    total: int = Field(0, description="Tổng lượt xử lý trong ngày")
    success: int = Field(0, description="Số lượt thành công")
    failed: int = Field(0, description="Số lượt thất bại")
    pending_review: int = Field(0, description="Số lượt chờ duyệt")


class AdminActivitySummary(BaseModel):
    new_users: int = Field(0, description="Số người dùng mới đăng ký trong kỳ")
    transactions: int = Field(0, description="Số giao dịch tạo mới trong kỳ")
    voice_processing: int = Field(0, description="Số lượt xử lý giọng nói trong kỳ")


class AdminActivityTrendItem(BaseModel):
    date: str = Field(..., description="Ngày (YYYY-MM-DD)")
    new_users: int = Field(0, description="Số người dùng mới")
    transactions: int = Field(0, description="Số giao dịch")
    voice_processing: int = Field(0, description="Số lượt xử lý giọng nói")


class AdminDatasetSummary(BaseModel):
    voice_records: int = Field(0, description="Tổng số bản ghi voice records")
    dataset_records: int = Field(0, description="Số bản ghi đạt chuẩn dataset (thành công, có transcript)")
    corrections: int = Field(0, description="Số bản ghi có chỉnh sửa / feedback")
    evaluation_records: Optional[int] = Field(None, description="Số bản ghi evaluation (nếu có)")


class AdminRecentActivityItem(BaseModel):
    id: int = Field(..., description="Mã định danh hoạt động")
    timestamp: Optional[str] = Field(None, description="Thời điểm phát sinh (ISO 8601)")
    module: str = Field("VOICE", description="Phân hệ (VOICE, USER, TRANSACTION...)")
    action: str = Field("PROCESS", description="Hành động thực hiện")
    status: str = Field("SUCCESS", description="Trạng thái (SUCCESS, FAILED...)")
    description: Optional[str] = Field(None, description="Mô tả tóm tắt hoạt động")


class AdminSystemHealth(BaseModel):
    api: str = Field("healthy", description="Trạng thái API Backend")
    database: str = Field("healthy", description="Trạng thái kết nối cơ sở dữ liệu")
    ai_service: str = Field("healthy", description="Trạng thái AI Service")


class AdminDashboardResponse(BaseModel):
    period: AdminDashboardPeriod = Field(..., description="Thông tin kỳ báo cáo và khoảng thời gian")
    system: AdminSystemSummary = Field(..., description="Tổng quan chỉ số hệ thống toàn thời gian")
    voice_processing: AdminVoiceProcessingSummary = Field(..., description="Chỉ số xử lý giọng nói theo kỳ lọc")
    voice_processing_trend: List[AdminVoiceProcessingTrendItem] = Field(default_factory=list, description="Xu hướng xử lý giọng nói theo ngày")
    activity: AdminActivitySummary = Field(..., description="Hoạt động hệ thống theo kỳ lọc")
    activity_trend: List[AdminActivityTrendItem] = Field(default_factory=list, description="Xu hướng hoạt động hệ thống theo ngày")
    dataset: AdminDatasetSummary = Field(..., description="Tổng quan dữ liệu Data Lake / Dataset")
    recent_activity: List[AdminRecentActivityItem] = Field(default_factory=list, description="Lịch sử hoạt động gần đây của hệ thống")
    system_health: AdminSystemHealth = Field(..., description="Tình trạng hoạt động của các dịch vụ hệ thống")
    # Tương thích ngược nếu client cũ đọc trường summary
    summary: Optional[Dict[str, Any]] = Field(None, description="Trường tương thích ngược cho client cũ")


# Alias tương thích ngược
AdminDashboardSummaryResponse = AdminDashboardResponse


class AdminDashboardTrendItem(BaseModel):
    date: str = Field(..., description="Mốc thời gian (YYYY-MM-DD)")
    new_users: int = Field(0, description="Người dùng mới")
    transactions: int = Field(0, description="Số giao dịch")
    voice_processing: int = Field(0, description="Lượt xử lý giọng nói")
    revenue: float = Field(0.0, description="Tương thích ngược")
    expense: float = Field(0.0, description="Tương thích ngược")
    profit: float = Field(0.0, description="Tương thích ngược")
    transaction_count: int = Field(0, description="Tương thích ngược")


class AdminDashboardTopProductItem(BaseModel):
    product_id: int = Field(0, description="ID sản phẩm")
    product_name: str = Field("", description="Tên sản phẩm")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    quantity_sold: float = Field(0.0, description="Số lượng")
    revenue: float = Field(0.0, description="Doanh thu")


class AdminDashboardExpenseCategoryItem(BaseModel):
    category_id: Optional[int] = Field(None, description="ID danh mục")
    category_name: str = Field("", description="Tên danh mục")
    amount: float = Field(0.0, description="Số tiền")
