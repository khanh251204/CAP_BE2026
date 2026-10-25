"""
Admin Closing Management — Service Layer

Admin quản lý chốt sổ của toàn bộ người dùng (cross-user):
- Thống kê tổng quan, danh sách / chi tiết kỳ chốt, drill-down giao dịch.
- Mở lại kỳ chốt (bắt buộc lý do) và chốt lại kỳ đang mở.
- Theo dõi & gửi lại email báo cáo chốt sổ.
- Xem / chỉnh cấu hình tự động chốt sổ của từng user.

Nghiệp vụ chốt sổ dùng lại ClosingService (không viết lại logic snapshot).
Không bao giờ xóa cứng kỳ chốt: lịch sử chốt sổ là dữ liệu kế toán.
Mọi thao tác ghi đều được ghi vết vào System Log.
"""
import logging
from datetime import date, datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import cast, desc, func, or_, String
from sqlalchemy.orm import Session, joinedload

from app.models.closing_period_model import ClosingPeriod
from app.models.closing_report_model import ClosingReport
from app.models.closing_setting_model import ClosingSetting
from app.models.closing_transaction_model import ClosingTransaction
from app.models.user_model import User
from app.services.closing_service import ClosingService

logger = logging.getLogger(__name__)

PERIOD_TYPES = ("DAY", "MONTH", "QUARTER", "YEAR")
PERIOD_STATUSES = ("CLOSED", "OPEN", "REOPENED")
REPORT_STATUSES = ("PENDING", "SENT", "FAILED")

PERIOD_SORT_COLUMNS = {
    "closed_at": ClosingPeriod.closed_at,
    "created_at": ClosingPeriod.created_at,
    "period_start": ClosingPeriod.period_start,
    "period_end": ClosingPeriod.period_end,
    "total_sales": ClosingPeriod.total_sales,
    "total_income": ClosingPeriod.total_income,
    "total_expense": ClosingPeriod.total_expense,
    "closing_id": ClosingPeriod.closing_id,
}


# =============================================
# HELPERS
# =============================================

def _pagination(page: int, limit: int, total: int) -> Dict[str, int]:
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": ceil(total / limit) if limit > 0 else 0,
    }


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _upper_choice(value: Optional[str], allowed: tuple, field: str) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip().upper()
    if v not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} không hợp lệ. Chỉ chấp nhận: {', '.join(allowed)}."
        )
    return v


def _user_brief(user: Optional[User]) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "business_type": user.business_type,
        "store_name": user.store_name,
    }


def _serialize_period(
    period: ClosingPeriod,
    tx_count: int = 0,
    failed_reports: int = 0,
) -> Dict[str, Any]:
    return {
        "closing_id": period.closing_id,
        "user_id": period.user_id,
        "user": _user_brief(period.user),
        "period_type": period.period_type,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "total_sales": period.total_sales or 0,
        "total_purchase": period.total_purchase or 0,
        "total_income": period.total_income or 0,
        "total_expense": period.total_expense or 0,
        "total_receivable": period.total_receivable or 0,
        "total_payable": period.total_payable or 0,
        "total_inventory_value": period.total_inventory_value or 0,
        "status": period.status,
        "note": period.note,
        "closed_at": _iso(period.closed_at),
        "created_at": _iso(period.created_at),
        "transaction_count": tx_count,
        "failed_report_count": failed_reports,
    }


def _serialize_report(report: ClosingReport) -> Dict[str, Any]:
    period = report.closing_period
    return {
        "report_id": report.report_id,
        "closing_id": report.closing_id,
        "user_id": report.user_id,
        "user": _user_brief(report.user),
        "report_type": report.report_type,
        "recipient_email": report.recipient_email,
        "send_status": report.send_status,
        "sent_at": _iso(report.sent_at),
        "error_message": report.error_message,
        "created_at": _iso(report.created_at) or "",
        "period_type": period.period_type if period else None,
        "period_start": _iso(period.period_start) if period else None,
        "period_end": _iso(period.period_end) if period else None,
    }


def _serialize_setting(setting: ClosingSetting) -> Dict[str, Any]:
    return {
        "setting_id": setting.setting_id,
        "user_id": setting.user_id,
        "user": _user_brief(setting.user),
        "period_type": setting.period_type,
        "closing_time": setting.closing_time.strftime("%H:%M:%S") if setting.closing_time else "",
        "auto_close": bool(setting.auto_close),
        "send_report": bool(setting.send_report),
        "report_channel": setting.report_channel,
        "timezone": setting.timezone,
        "is_active": bool(setting.is_active),
        "updated_at": _iso(setting.updated_at),
    }


def _period_params_from_period(period: ClosingPeriod) -> Dict[str, Any]:
    """Dựng lại tham số PeriodService từ một kỳ đã lưu (dùng khi Admin chốt lại kỳ)."""
    start: date = period.period_start
    if period.period_type == "DAY":
        return {"period_type": "DAY", "date_val": start}
    if period.period_type == "MONTH":
        return {"period_type": "MONTH", "year": start.year, "month": start.month}
    if period.period_type == "QUARTER":
        return {"period_type": "QUARTER", "year": start.year, "quarter": (start.month - 1) // 3 + 1}
    return {"period_type": "YEAR", "year": start.year}


def _audit(admin_id: int, action: str, message: str, detail: Dict[str, Any]) -> None:
    """Ghi vết thao tác Admin vào System Log (không làm hỏng luồng chính nếu lỗi)."""
    try:
        from app.services.system_log_service import log_event
        log_event(
            level="INFO",
            step="ADMIN_CLOSING",
            message=message,
            detail={"action": action, "admin_id": admin_id, **detail},
            user_id=admin_id,
            api_path="/admin/closing",
        )
    except Exception as e:
        logger.warning(f"[AdminClosing] Không ghi được audit log: {e}")


def _notify_owner(user_id: int, title: str, description: str) -> None:
    try:
        from app.services.notification_service import NotificationService
        NotificationService.create_notification({
            "userId": str(user_id),
            "title": title,
            "description": description,
            "notificationType": "CLOSING",
            "icon": "lock-open",
            "iconColor": "#FFFFFF",
            "borderColor": "#B45309",
            "isRead": False,
        })
    except Exception as e:
        logger.warning(f"[AdminClosing] Không gửi được thông báo cho user {user_id}: {e}")


class AdminClosingService:

    # =============================================
    # OVERVIEW
    # =============================================
    @staticmethod
    def get_overview(db: Session) -> Dict[str, Any]:
        by_status = {s: 0 for s in PERIOD_STATUSES}
        for st, cnt in db.query(ClosingPeriod.status, func.count()).group_by(ClosingPeriod.status).all():
            by_status[str(st)] = cnt

        by_type = {t: 0 for t in PERIOD_TYPES}
        for pt, cnt in db.query(ClosingPeriod.period_type, func.count()).group_by(ClosingPeriod.period_type).all():
            by_type[str(pt)] = cnt

        reports = {s: 0 for s in REPORT_STATUSES}
        for st, cnt in db.query(ClosingReport.send_status, func.count()).group_by(ClosingReport.send_status).all():
            reports[str(st)] = cnt

        week_ago = datetime.now() - timedelta(days=7)

        return {
            "total_periods": sum(by_status.values()),
            "by_status": by_status,
            "by_period_type": by_type,
            "users_with_closings": db.query(func.count(func.distinct(ClosingPeriod.user_id))).scalar() or 0,
            "closed_last_7_days": db.query(func.count(ClosingPeriod.closing_id)).filter(
                ClosingPeriod.status == "CLOSED",
                ClosingPeriod.closed_at >= week_ago,
            ).scalar() or 0,
            "open_periods": by_status.get("OPEN", 0) + by_status.get("REOPENED", 0),
            "reports_by_status": reports,
            "settings_total": db.query(func.count(ClosingSetting.setting_id)).scalar() or 0,
            "auto_close_enabled": db.query(func.count(ClosingSetting.setting_id)).filter(
                ClosingSetting.auto_close == True,  # noqa: E712
                ClosingSetting.is_active == True,  # noqa: E712
            ).scalar() or 0,
            "settings_inactive": db.query(func.count(ClosingSetting.setting_id)).filter(
                ClosingSetting.is_active == False  # noqa: E712
            ).scalar() or 0,
        }

    # =============================================
    # LIST CLOSING PERIODS (cross-user)
    # =============================================
    @staticmethod
    def list_periods(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        period_type: Optional[str] = None,
        status_val: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        sort_by: str = "closed_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        period_type = _upper_choice(period_type, PERIOD_TYPES, "period_type")
        status_val = _upper_choice(status_val, PERIOD_STATUSES, "status")

        query = db.query(ClosingPeriod).options(
            joinedload(ClosingPeriod.user).joinedload(User.store_rel)
        )

        if user_id is not None:
            query = query.filter(ClosingPeriod.user_id == user_id)
        if period_type:
            query = query.filter(ClosingPeriod.period_type == period_type)
        if status_val:
            query = query.filter(ClosingPeriod.status == status_val)
        # Kỳ giao với khoảng [from, to]
        if date_from:
            query = query.filter(ClosingPeriod.period_end >= date_from)
        if date_to:
            query = query.filter(ClosingPeriod.period_start <= date_to)
        if search and search.strip():
            term = search.strip()
            query = query.join(User, ClosingPeriod.user_id == User.user_id).filter(or_(
                cast(ClosingPeriod.closing_id, String) == term,
                User.full_name.ilike(f"%{term}%"),
                User.email.ilike(f"%{term}%"),
                ClosingPeriod.note.ilike(f"%{term}%"),
            ))

        total = query.count()

        sort_col = PERIOD_SORT_COLUMNS.get(sort_by or "closed_at", ClosingPeriod.closed_at)
        order = desc(sort_col) if (sort_order or "desc").lower() == "desc" else sort_col.asc()
        rows = (
            query.order_by(order, desc(ClosingPeriod.closing_id))
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        tx_counts, failed_counts = AdminClosingService._counts_for([r.closing_id for r in rows], db)
        items = [
            _serialize_period(r, tx_counts.get(r.closing_id, 0), failed_counts.get(r.closing_id, 0))
            for r in rows
        ]
        return {"items": items, "pagination": _pagination(page, limit, total)}

    @staticmethod
    def _counts_for(closing_ids: List[int], db: Session):
        """Đếm giao dịch & email lỗi cho nhiều kỳ bằng 2 query (tránh N+1)."""
        if not closing_ids:
            return {}, {}
        tx_counts = dict(
            db.query(ClosingTransaction.closing_id, func.count(ClosingTransaction.transaction_id))
            .filter(ClosingTransaction.closing_id.in_(closing_ids))
            .group_by(ClosingTransaction.closing_id)
            .all()
        )
        failed_counts = dict(
            db.query(ClosingReport.closing_id, func.count(ClosingReport.report_id))
            .filter(ClosingReport.closing_id.in_(closing_ids), ClosingReport.send_status == "FAILED")
            .group_by(ClosingReport.closing_id)
            .all()
        )
        return tx_counts, failed_counts

    # =============================================
    # PERIOD DETAIL
    # =============================================
    @staticmethod
    def _get_period_or_404(db: Session, closing_id: int) -> ClosingPeriod:
        period = (
            db.query(ClosingPeriod)
            .options(joinedload(ClosingPeriod.user).joinedload(User.store_rel))
            .filter(ClosingPeriod.closing_id == closing_id)
            .first()
        )
        if not period:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id}."
            )
        return period

    @staticmethod
    def get_period_detail(db: Session, closing_id: int) -> Dict[str, Any]:
        period = AdminClosingService._get_period_or_404(db, closing_id)
        tx_counts, failed_counts = AdminClosingService._counts_for([closing_id], db)

        reports = (
            db.query(ClosingReport)
            .filter(ClosingReport.closing_id == closing_id)
            .order_by(desc(ClosingReport.created_at))
            .all()
        )
        data = _serialize_period(period, tx_counts.get(closing_id, 0), failed_counts.get(closing_id, 0))
        data["reports"] = [
            {
                "report_id": r.report_id,
                "closing_id": r.closing_id,
                "user_id": r.user_id,
                "report_type": r.report_type,
                "recipient_email": r.recipient_email,
                "send_status": r.send_status,
                "sent_at": _iso(r.sent_at),
                "error_message": r.error_message,
                "created_at": _iso(r.created_at) or "",
            }
            for r in reports
        ]
        return data

    @staticmethod
    def get_period_transactions(db: Session, closing_id: int, page: int, limit: int) -> Dict[str, Any]:
        period = AdminClosingService._get_period_or_404(db, closing_id)
        return ClosingService.get_closing_transactions(
            db=db,
            user_id=period.user_id,
            closing_id=closing_id,
            page=page,
            page_size=limit,
        )

    # =============================================
    # REOPEN / RE-CLOSE
    # =============================================
    @staticmethod
    def reopen_period(
        db: Session,
        closing_id: int,
        admin_id: int,
        reason: str,
        notify_user: bool = True,
    ) -> Dict[str, Any]:
        period = AdminClosingService._get_period_or_404(db, closing_id)
        if period.status != "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kỳ chốt sổ #{closing_id} đang ở trạng thái {period.status}, không thể mở lại."
            )

        ClosingService.reopen_closing(
            db=db,
            user_id=period.user_id,
            closing_id=closing_id,
            reason=f"Admin #{admin_id}: {reason.strip()}",
        )

        _audit(admin_id, "REOPEN", f"Admin mở lại kỳ chốt sổ #{closing_id}", {
            "closing_id": closing_id,
            "owner_user_id": period.user_id,
            "reason": reason,
        })
        if notify_user:
            _notify_owner(
                period.user_id,
                f"Kỳ chốt sổ {period.period_type} đã được mở lại",
                f"Quản trị viên đã mở lại kỳ {period.period_start} đến {period.period_end}. Lý do: {reason.strip()}",
            )
        return AdminClosingService.get_period_detail(db, closing_id)

    @staticmethod
    def reclose_period(
        db: Session,
        closing_id: int,
        admin_id: int,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Chốt lại một kỳ đang mở: tính lại snapshot và liên kết giao dịch từ dữ liệu hiện tại."""
        period = AdminClosingService._get_period_or_404(db, closing_id)
        if period.status == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kỳ chốt sổ #{closing_id} đã ở trạng thái CLOSED."
            )

        owner_id = period.user_id
        # create_closing chỉ cập nhật lại bản ghi khi status == OPEN; chuẩn hóa REOPENED về OPEN
        # để không tạo bản ghi trùng kỳ (vi phạm uk_user_closing_period).
        if period.status != "OPEN":
            period.status = "OPEN"
            db.flush()

        try:
            ClosingService.create_closing(
                db=db,
                user_id=owner_id,
                period_params=_period_params_from_period(period),
                note=note or f"Chốt lại bởi Admin #{admin_id}",
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[AdminClosing] Lỗi chốt lại kỳ #{closing_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi khi chốt lại kỳ chốt sổ."
            )

        _audit(admin_id, "RECLOSE", f"Admin chốt lại kỳ chốt sổ #{closing_id}", {
            "closing_id": closing_id,
            "owner_user_id": owner_id,
            "note": note,
        })
        return AdminClosingService.get_period_detail(db, closing_id)

    # =============================================
    # REPORTS (EMAIL LOG)
    # =============================================
    @staticmethod
    def list_reports(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        closing_id: Optional[int] = None,
        status_val: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        status_val = _upper_choice(status_val, REPORT_STATUSES, "status")

        query = db.query(ClosingReport).options(
            joinedload(ClosingReport.user).joinedload(User.store_rel),
            joinedload(ClosingReport.closing_period),
        )
        if user_id is not None:
            query = query.filter(ClosingReport.user_id == user_id)
        if closing_id is not None:
            query = query.filter(ClosingReport.closing_id == closing_id)
        if status_val:
            query = query.filter(ClosingReport.send_status == status_val)
        if date_from:
            query = query.filter(ClosingReport.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            query = query.filter(ClosingReport.created_at <= datetime.combine(date_to, datetime.max.time()))
        if search and search.strip():
            term = search.strip()
            query = query.filter(or_(
                ClosingReport.recipient_email.ilike(f"%{term}%"),
                ClosingReport.error_message.ilike(f"%{term}%"),
            ))

        total = query.count()
        rows = (
            query.order_by(desc(ClosingReport.created_at), desc(ClosingReport.report_id))
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return {
            "items": [_serialize_report(r) for r in rows],
            "pagination": _pagination(page, limit, total),
        }

    @staticmethod
    def resend_report(db: Session, report_id: int, admin_id: int) -> Dict[str, Any]:
        report = db.query(ClosingReport).filter(ClosingReport.report_id == report_id).first()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi gửi báo cáo ID {report_id}."
            )
        owner_id = report.user_id
        try:
            result = ClosingService.resend_closing_report(db=db, user_id=owner_id, report_id=report_id)
        finally:
            _audit(admin_id, "RESEND_REPORT", f"Admin gửi lại email báo cáo chốt sổ #{report_id}", {
                "report_id": report_id,
                "closing_id": report.closing_id,
                "owner_user_id": owner_id,
                "send_status": report.send_status,
            })
        return result

    # =============================================
    # SETTINGS
    # =============================================
    @staticmethod
    def list_settings(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        period_type: Optional[str] = None,
        auto_close: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        period_type = _upper_choice(period_type, PERIOD_TYPES, "period_type")

        query = db.query(ClosingSetting).options(
            joinedload(ClosingSetting.user).joinedload(User.store_rel)
        )
        if user_id is not None:
            query = query.filter(ClosingSetting.user_id == user_id)
        if period_type:
            query = query.filter(ClosingSetting.period_type == period_type)
        if auto_close is not None:
            query = query.filter(ClosingSetting.auto_close == auto_close)
        if is_active is not None:
            query = query.filter(ClosingSetting.is_active == is_active)
        if search and search.strip():
            term = search.strip()
            query = query.join(User, ClosingSetting.user_id == User.user_id).filter(or_(
                User.full_name.ilike(f"%{term}%"),
                User.email.ilike(f"%{term}%"),
            ))

        total = query.count()
        rows = (
            query.order_by(desc(ClosingSetting.updated_at), desc(ClosingSetting.setting_id))
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return {
            "items": [_serialize_setting(s) for s in rows],
            "pagination": _pagination(page, limit, total),
        }

    @staticmethod
    def update_user_setting(
        db: Session,
        user_id: int,
        admin_id: int,
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy người dùng ID {user_id}."
            )

        # Kiểm tra chặt hơn API của user: cấu hình sai sẽ làm scheduler chạy lỗi
        tz = update_data.get("timezone")
        if tz is not None:
            try:
                ZoneInfo(tz)
            except (ZoneInfoNotFoundError, ValueError):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"timezone '{tz}' không hợp lệ.")
        channel = update_data.get("report_channel")
        if channel is not None:
            update_data["report_channel"] = _upper_choice(channel, ("EMAIL",), "report_channel")

        before = db.query(ClosingSetting).filter(ClosingSetting.user_id == user_id).first()
        before_data = _serialize_setting(before) if before else None

        ClosingService.update_closing_settings(db=db, user_id=user_id, update_data=update_data)

        _audit(admin_id, "UPDATE_SETTING", f"Admin cập nhật cấu hình chốt sổ của user #{user_id}", {
            "owner_user_id": user_id,
            "changes": update_data,
            "before": {k: v for k, v in (before_data or {}).items() if k != "user"},
        })

        setting = (
            db.query(ClosingSetting)
            .options(joinedload(ClosingSetting.user).joinedload(User.store_rel))
            .filter(ClosingSetting.user_id == user_id)
            .first()
        )
        return _serialize_setting(setting)
