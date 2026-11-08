from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.admin_system_log_schema import PaginationInfo


class AuditLogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    entity_type: str
    entity_id: Optional[int] = None
    transaction_id: Optional[int] = None
    action: str
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_role: str
    source: Optional[str] = None
    request_id: Optional[str] = None
    api_path: Optional[str] = None
    http_method: Optional[str] = None
    before_data: Optional[Dict[str, Any]] = None
    after_data: Optional[Dict[str, Any]] = None
    changes: Optional[Dict[str, Any]] = None


class AuditLogListResponse(BaseModel):
    success: bool = True
    data: List[AuditLogItemResponse]
    pagination: PaginationInfo


class AuditLogSummaryData(BaseModel):
    total: int
    create_count: int
    update_count: int
    delete_count: int
    admin_actions: int
    distinct_transactions: int


class AuditLogSummaryResponse(BaseModel):
    success: bool = True
    data: AuditLogSummaryData


# ---------------------------------------------------------------- AI Monitoring

class CorrectedFieldCount(BaseModel):
    field: str
    count: int


class IntentCorrectionRate(BaseModel):
    intent: str
    confirmed: int
    corrected: int
    correction_rate: float
    failed: int
    top_corrected_fields: List[CorrectedFieldCount] = []


class CorrectionRateTotals(BaseModel):
    confirmed: int
    corrected: int
    correction_rate: float
    failed: int
    # Hiệu chỉnh không gắn được với bản ghi giọng nói (vd. câu gõ tay): vẫn được đếm riêng
    corrections_without_voice_record: int


class CorrectionRateData(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    totals: CorrectionRateTotals
    by_intent: List[IntentCorrectionRate]


class CorrectionRateResponse(BaseModel):
    success: bool = True
    data: CorrectionRateData
