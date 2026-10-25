"""
Admin Closing Management — Router

Endpoints:
  GET   /admin/closing/overview                       — Thống kê tổng quan chốt sổ toàn hệ thống
  GET   /admin/closing/periods                        — Danh sách kỳ chốt (cross-user, filter, sort, phân trang)
  GET   /admin/closing/periods/{id}                   — Chi tiết kỳ chốt + lịch sử email
  GET   /admin/closing/periods/{id}/transactions      — Drill-down giao dịch thuộc kỳ
  PATCH /admin/closing/periods/{id}                   — Đổi trạng thái: OPEN (mở lại, bắt buộc lý do) / CLOSED (chốt lại)
  GET   /admin/closing/reports                        — Lịch sử gửi email báo cáo chốt sổ
  POST  /admin/closing/reports/{id}/deliveries        — Gửi lại email báo cáo
  GET   /admin/closing/settings                       — Cấu hình tự động chốt sổ của các user
  PUT   /admin/closing/settings/{user_id}             — Cập nhật cấu hình chốt sổ của một user

Authorization: JWT + quyền admin_closing:* (require_permission). Không có API xóa kỳ chốt (dữ liệu kế toán).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authenticate_user, require_permission, require_admin_area
from app.schemas.admin_closing_schema import (
    AdminClosingOverviewResponse,
    AdminClosingPeriodDetailResponse,
    AdminClosingPeriodListResponse,
    AdminClosingStatusUpdateRequest,
    AdminClosingReportListResponse,
    AdminClosingSettingItem,
    AdminClosingSettingListResponse,
)
from app.schemas.closing_schema import ClosingSettingUpdateRequest, ClosingTransactionsResponse
from app.services.admin_closing_service import AdminClosingService


router = APIRouter(
    prefix="/admin/closing",
    tags=["Admin - Closing Management"],
    dependencies=[Depends(require_admin_area)]
)


def _admin_id(current_admin: dict) -> int:
    return int(current_admin.get("sub", 0))


# =========================================================
# OVERVIEW
# =========================================================
@router.get(
    "/overview",
    response_model=AdminClosingOverviewResponse,
    summary="Thống kê tổng quan chốt sổ (Admin)",
    dependencies=[Depends(require_permission("admin_closing:read"))],
)
def get_overview(db: Session = Depends(get_db)):
    return AdminClosingService.get_overview(db)


# =========================================================
# CLOSING PERIODS
# =========================================================
@router.get(
    "/periods",
    response_model=AdminClosingPeriodListResponse,
    summary="Danh sách kỳ chốt sổ của toàn hệ thống (Admin)",
    description=(
        "Tìm theo mã kỳ chốt, tên/email chủ sổ, ghi chú. Lọc theo user, loại kỳ, trạng thái "
        "và khoảng ngày (kỳ giao với [from, to])."
    ),
    dependencies=[Depends(require_permission("admin_closing:read"))],
)
def list_periods(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Mã kỳ chốt, tên/email chủ sổ, ghi chú"),
    user_id: Optional[int] = Query(None, description="Lọc theo chủ sổ"),
    period_type: Optional[str] = Query(None, description="DAY, MONTH, QUARTER, YEAR"),
    status_val: Optional[str] = Query(None, alias="status", description="CLOSED, OPEN, REOPENED"),
    date_from: Optional[date] = Query(None, alias="from", description="YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, alias="to", description="YYYY-MM-DD"),
    sort_by: str = Query(
        "closed_at",
        description="closed_at, created_at, period_start, period_end, total_sales, total_income, total_expense, closing_id",
    ),
    sort_order: str = Query("desc", description="asc hoặc desc"),
    db: Session = Depends(get_db),
):
    return AdminClosingService.list_periods(
        db=db,
        page=page,
        limit=limit,
        search=search,
        user_id=user_id,
        period_type=period_type,
        status_val=status_val,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/periods/{closing_id}",
    response_model=AdminClosingPeriodDetailResponse,
    summary="Chi tiết kỳ chốt sổ (Admin)",
    dependencies=[Depends(require_permission("admin_closing:read"))],
)
def get_period_detail(
    closing_id: int = Path(..., description="ID kỳ chốt"),
    db: Session = Depends(get_db),
):
    return AdminClosingService.get_period_detail(db, closing_id)


@router.get(
    "/periods/{closing_id}/transactions",
    response_model=ClosingTransactionsResponse,
    summary="Danh sách giao dịch thuộc kỳ chốt (Admin)",
    dependencies=[Depends(require_permission("admin_closing:read"))],
)
def get_period_transactions(
    closing_id: int = Path(..., description="ID kỳ chốt"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return AdminClosingService.get_period_transactions(db, closing_id, page, limit)


@router.patch(
    "/periods/{closing_id}",
    response_model=AdminClosingPeriodDetailResponse,
    summary="Mở lại / chốt lại kỳ chốt (Admin)",
    description=(
        "status = OPEN: chuyển kỳ CLOSED về OPEN để chủ sổ điều chỉnh giao dịch (bắt buộc lý do, thao tác được ghi vết). "
        "status = CLOSED: tính lại snapshot từ dữ liệu hiện tại, liên kết lại giao dịch và gửi email báo cáo cho chủ sổ."
    ),
    dependencies=[Depends(require_permission("admin_closing:manage"))],
)
def update_period_status(
    data: AdminClosingStatusUpdateRequest,
    closing_id: int = Path(..., description="ID kỳ chốt"),
    current_admin: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    if data.status == "OPEN":
        return AdminClosingService.reopen_period(
            db=db,
            closing_id=closing_id,
            admin_id=_admin_id(current_admin),
            reason=data.reason,
            notify_user=data.notify_user,
        )
    return AdminClosingService.reclose_period(
        db=db,
        closing_id=closing_id,
        admin_id=_admin_id(current_admin),
        note=data.note,
    )


# =========================================================
# REPORTS (EMAIL LOG)
# =========================================================
@router.get(
    "/reports",
    response_model=AdminClosingReportListResponse,
    summary="Lịch sử gửi email báo cáo chốt sổ (Admin)",
    dependencies=[Depends(require_permission("admin_closing:read"))],
)
def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Email nhận hoặc nội dung lỗi"),
    user_id: Optional[int] = Query(None),
    closing_id: Optional[int] = Query(None),
    status_val: Optional[str] = Query(None, alias="status", description="PENDING, SENT, FAILED"),
    date_from: Optional[date] = Query(None, alias="from", description="YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, alias="to", description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    return AdminClosingService.list_reports(
        db=db,
        page=page,
        limit=limit,
        search=search,
        user_id=user_id,
        closing_id=closing_id,
        status_val=status_val,
        date_from=date_from,
        date_to=date_to,
    )


@router.post(
    "/reports/{report_id}/deliveries",
    status_code=201,
    summary="Gửi lại email báo cáo chốt sổ (Admin)",
    dependencies=[Depends(require_permission("admin_closing:manage"))],
)
def resend_report(
    report_id: int = Path(..., description="ID bản ghi gửi báo cáo"),
    current_admin: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    return AdminClosingService.resend_report(db, report_id, _admin_id(current_admin))


# =========================================================
# SETTINGS
# =========================================================
@router.get(
    "/settings",
    response_model=AdminClosingSettingListResponse,
    summary="Cấu hình tự động chốt sổ của các user (Admin)",
    dependencies=[Depends(require_permission("admin_closing:read"))],
)
def list_settings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Tên hoặc email user"),
    user_id: Optional[int] = Query(None),
    period_type: Optional[str] = Query(None, description="DAY, MONTH, QUARTER, YEAR"),
    auto_close: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    return AdminClosingService.list_settings(
        db=db,
        page=page,
        limit=limit,
        search=search,
        user_id=user_id,
        period_type=period_type,
        auto_close=auto_close,
        is_active=is_active,
    )


@router.put(
    "/settings/{user_id}",
    response_model=AdminClosingSettingItem,
    summary="Cập nhật cấu hình chốt sổ của một user (Admin)",
    description="Ví dụ: tắt tự động chốt cho user đang bị lỗi, đổi giờ chốt hoặc múi giờ. Thao tác được ghi vết.",
    dependencies=[Depends(require_permission("admin_closing:manage"))],
)
def update_user_setting(
    data: ClosingSettingUpdateRequest,
    user_id: int = Path(..., description="ID user"),
    current_admin: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    return AdminClosingService.update_user_setting(
        db=db,
        user_id=user_id,
        admin_id=_admin_id(current_admin),
        update_data=data.model_dump(exclude_unset=True),
    )
