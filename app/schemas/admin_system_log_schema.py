from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DeviceInfoSchema(BaseModel):
    platform: Optional[str] = None
    os_version: Optional[str] = None


class SystemLogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    level: str
    step: Optional[str] = None
    api_path: Optional[str] = None
    http_method: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    message: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    user_id: Optional[int] = None
    device: Optional[Dict[str, Any]] = None
    app_version: Optional[str] = None


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class SystemLogListResponse(BaseModel):
    success: bool = True
    data: List[SystemLogItemResponse]
    pagination: PaginationInfo


class SystemLogSummaryData(BaseModel):
    date: str
    total_requests: int
    success_rate: float
    error_count: int
    warning_count: int
    avg_processing_ms: float
    p95_processing_ms: float


class SystemLogSummaryResponse(BaseModel):
    success: bool = True
    data: SystemLogSummaryData
