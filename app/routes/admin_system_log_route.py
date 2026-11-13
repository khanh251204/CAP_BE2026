from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.configs import system_log_settings as log_settings
from app.configs.database import get_db
from app.configs.jwt import require_permission, require_admin_area
from app.schemas.admin_system_log_schema import (
    SystemLogListResponse,
    SystemLogSettingsResponse,
    SystemLogSettingsUpdate,
    SystemLogSummaryResponse,
)
from app.services.admin_system_log_service import AdminSystemLogService

router = APIRouter(
    prefix="/admin/system-logs",
    tags=["Admin - System Logs"],
    dependencies=[Depends(require_admin_area)]
)


@router.get(
    "/summary",
    response_model=SystemLogSummaryResponse,
    summary="Thống kê tổng quan sức khỏe hệ thống theo ngày",
    description="Tính toán các chỉ số sức khỏe hệ thống theo ngày: tổng requests, tỷ lệ thành công, số lỗi, cảnh báo, thời gian xử lý trung bình và P95.",
    dependencies=[Depends(require_permission("system:log_read"))],
)
def get_system_logs_summary(
    date: Optional[str] = Query(None, description="Ngày cần thống kê theo định dạng YYYY-MM-DD (mặc định là hôm nay)"),
    db: Session = Depends(get_db)
):
    summary_data = AdminSystemLogService.get_summary(db=db, target_date_str=date)
    return {
        "success": True,
        "data": summary_data
    }


@router.get(
    "",
    response_model=SystemLogListResponse,
    summary="Xem danh sách System Logs",
    description="Truy vấn danh sách System Logs có phân trang và bộ lọc theo level, step, khoảng thời gian, từ khóa tìm kiếm.",
    dependencies=[Depends(require_permission("system:log_read"))],
)
def list_system_logs(
    level: Optional[str] = Query(None, description="Lọc theo level: INFO, WARNING, ERROR"),
    step: Optional[str] = Query(None, description="Lọc theo bước phát sinh: AUTH, STT, LLM, DB, OTHER"),
    date_from: Optional[datetime] = Query(None, alias="date_from", description="Thời điểm bắt đầu (ISO 8601)"),
    date_to: Optional[datetime] = Query(None, alias="date_to", description="Thời điểm kết thúc (ISO 8601)"),
    keyword: Optional[str] = Query(None, description="Từ khóa tìm kiếm trong message, api_path, request_id, user_id"),
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số bản ghi trên một trang"),
    db: Session = Depends(get_db)
):
    items, total_items, total_pages = AdminSystemLogService.list_logs(
        db=db,
        level=level,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
        step=step,
        page=page,
        page_size=page_size
    )

    return {
        "success": True,
        "data": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages
        }
    }


# ---------------------------------------------------------------- Cài đặt ghi log theo chức năng
@router.get(
    "/settings",
    response_model=SystemLogSettingsResponse,
    summary="Xem cài đặt ghi system log theo chức năng",
    description="Mức ghi log (ALL / WARNING / ERROR / OFF) của từng chức năng mobile; admin tạm thời OFF.",
    dependencies=[Depends(require_permission("system:log_read"))],
)
def get_system_log_settings():
    return {"success": True, "data": log_settings.describe()}


@router.put(
    "/settings",
    response_model=SystemLogSettingsResponse,
    summary="Sửa cài đặt ghi system log theo chức năng",
    description="Chỉ gửi chức năng cần đổi. Áp dụng ngay cho mọi worker (tối đa vài giây).",
)
def update_system_log_settings(
    body: SystemLogSettingsUpdate,
    user=Depends(require_permission("system:setting_manage")),
):
    try:
        data = log_settings.save_levels(body.levels, updated_by=_user_id(user))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"success": True, "message": "Đã lưu cài đặt ghi log", "data": data}


@router.post(
    "/settings/reset",
    response_model=SystemLogSettingsResponse,
    summary="Khôi phục cài đặt ghi log mặc định",
    dependencies=[Depends(require_permission("system:setting_manage"))],
)
def reset_system_log_settings():
    return {"success": True, "message": "Đã khôi phục cài đặt mặc định", "data": log_settings.reset_levels()}


def _user_id(user) -> Optional[int]:
    raw = user.get("sub") if isinstance(user, dict) else getattr(user, "user_id", None)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
