from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_admin_area, require_permission
from app.schemas.admin_audit_schema import (
    AuditLogListResponse,
    AuditLogSummaryResponse,
    CorrectionRateResponse,
)
from app.services.admin_ai_monitoring_service import AdminAiMonitoringService
from app.services.admin_audit_service import AdminAuditService

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Audit & AI Monitoring"],
    dependencies=[Depends(require_admin_area), Depends(require_permission("system:log_read"))],
)


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Nhật ký thay đổi giao dịch (Audit Log)",
    description="Ai tạo / sửa / xoá giao dịch, công nợ, biến động kho nào, lúc nào, trước và sau ra sao. Lọc theo loại đối tượng, hành động, người thực hiện, giao dịch, thời gian.",
)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="TRANSACTION, TRANSACTION_DETAIL, DEBT, DEBT_PAYMENT hoặc INVENTORY"),
    action: Optional[str] = Query(None, description="CREATE, UPDATE hoặc DELETE"),
    actor_role: Optional[str] = Query(None, description="USER, ADMIN hoặc SYSTEM"),
    transaction_id: Optional[int] = Query(None, description="Xem vết của một giao dịch"),
    user_id: Optional[int] = Query(None, description="Người thực hiện hoặc chủ dữ liệu"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total, pages = AdminAuditService.list_logs(
        db=db, entity_type=entity_type, action=action, actor_role=actor_role, transaction_id=transaction_id,
        user_id=user_id, date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )
    return {
        "success": True,
        "data": items,
        "pagination": {"page": page, "page_size": page_size, "total_items": total, "total_pages": pages},
    }


@router.get(
    "/audit-logs/summary",
    response_model=AuditLogSummaryResponse,
    summary="Thống kê Audit Log",
)
def audit_log_summary(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    return {"success": True, "data": AdminAuditService.summary(db=db, date_from=date_from, date_to=date_to)}


@router.get(
    "/audit-logs/transactions/{transaction_id}",
    summary="Vòng đời một giao dịch",
    description="Toàn bộ vết của một giao dịch (kể cả đã xoá), cũ trước mới sau.",
)
def transaction_timeline(transaction_id: int, db: Session = Depends(get_db)):
    return {"success": True, "data": AdminAuditService.transaction_timeline(db=db, transaction_id=transaction_id)}


@router.get(
    "/ai-monitoring/corrections",
    response_model=CorrectionRateResponse,
    summary="Tỉ lệ người dùng sửa bản nháp của AI theo từng lệnh",
    description="Tỉ lệ sửa = số lần ghi sổ có hiệu chỉnh / tổng số lần ghi sổ, theo intent, kèm các trường bị sửa nhiều nhất.",
)
def correction_rate_by_intent(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    return {
        "success": True,
        "data": AdminAiMonitoringService.correction_rate_by_intent(db=db, date_from=date_from, date_to=date_to),
    }


# ---------------------------------------------------------------- Cài đặt ghi vết / dung lượng log

from typing import Any, Dict

from fastapi import Body, HTTPException, status as http_status

from app.configs.jwt import get_current_user_id
from app.services import admin_setting_service
from app.services.app_setting_service import SettingError
from app.services.data_retention_service import run_retention
from app.services.system_log_service import log_event

_settings_perm = Depends(require_permission("system:setting_manage"))


@router.get(
    "/settings/observability",
    summary="Cài đặt ghi vết và dung lượng log",
    description="Cài đặt hiện hành, mặc định, và số dòng / dung lượng của Audit Log và system log.",
    dependencies=[_settings_perm],
)
def get_observability_settings(db: Session = Depends(get_db)):
    return {"success": True, "data": admin_setting_service.read_settings(db)}


@router.put(
    "/settings/observability",
    summary="Đổi cài đặt ghi vết",
    description=(
        "Chỉ gửi phần cần đổi, ví dụ {\"audit\": {\"enabled\": {\"INVENTORY\": true}, \"retention_days\": 180}, "
        "\"system_log\": {\"log_success_requests\": false}}. Sai khoá / sai kiểu / ngoài giới hạn thì 422 và không lưu gì."
    ),
    dependencies=[_settings_perm],
)
def update_observability_settings(
    patch: Dict[str, Any] = Body(...),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        data = admin_setting_service.update_settings(db, patch, current_user_id)
    except SettingError as exc:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    log_event("INFO", "ADMIN", "Admin đổi cài đặt ghi vết", detail={"patch": patch}, user_id=current_user_id)
    return {"success": True, "data": data}


@router.post(
    "/settings/observability/reset",
    summary="Khôi phục cài đặt ghi vết mặc định",
    dependencies=[_settings_perm],
)
def reset_observability_settings(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    data = admin_setting_service.reset_settings(db, current_user_id)
    log_event("INFO", "ADMIN", "Admin khôi phục cài đặt ghi vết mặc định", user_id=current_user_id)
    return {"success": True, "data": data}


@router.post(
    "/settings/observability/cleanup",
    summary="Dọn log cũ ngay",
    description="Xoá Audit Log và system log đã quá thời gian giữ theo cài đặt hiện hành (hệ thống cũng tự dọn mỗi ngày).",
    dependencies=[_settings_perm],
)
def cleanup_observability_data(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    result = run_retention(db)
    log_event("INFO", "ADMIN", "Admin dọn log cũ", detail=result, user_id=current_user_id)
    return {"success": True, "data": {**result, **{"usage": admin_setting_service.usage(db)}}}
