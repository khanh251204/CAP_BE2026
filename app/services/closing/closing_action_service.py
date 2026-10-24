import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.closing_period_model import ClosingPeriod
from app.models.closing_transaction_model import ClosingTransaction
from app.models.closing_report_model import ClosingReport
from app.models.transaction_model import Transaction
from app.models.product_model import Product
from app.models.user_model import User
from app.services.period_service import PeriodService
from app.services.report_service import ReportService
from app.services.websocket_manager import ws_manager
from app.services.closing.closing_email_service import ClosingEmailService
from app.services.closing.closing_guard import (
    assert_can_reopen,
    assert_no_reopened_children,
    period_params_of,
)

logger = logging.getLogger(__name__)


class ClosingActionService:
    @classmethod
    def preview_closing(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /closing-periods/preview:
        Tính toán trước số liệu sẽ chốt mà KHÔNG ghi vào DB.
        """
        period = PeriodService.resolve_period(**period_params)
        p_type = period["period_type"]
        p_start = period["period_start"]
        p_end = period["period_end"]

        if p_type not in ["DAY", "MONTH", "QUARTER", "YEAR"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ hỗ trợ xem trước chốt sổ cho các kỳ: DAY, MONTH, QUARTER, YEAR."
            )

        existing = db.query(ClosingPeriod).filter(
            ClosingPeriod.user_id == user_id,
            ClosingPeriod.period_type == p_type,
            ClosingPeriod.period_start == p_start,
            ClosingPeriod.period_end == p_end
        ).first()

        is_closed = (existing is not None and existing.status == "CLOSED")
        existing_id = existing.closing_id if existing else None

        live_data = ReportService.get_live_report(db, user_id, period_params)
        summary = live_data["summary"]

        inv_val_query = db.query(
            func.coalesce(
                func.sum(Product.min_quantity * 0), 0
            )
        ).filter(Product.user_id == user_id).scalar() or Decimal("0.00")

        return {
            "period_type": p_type,
            "period_start": p_start.isoformat(),
            "period_end": p_end.isoformat(),
            "is_closed": is_closed,
            "existing_closing_id": existing_id,
            "summary": summary,
            "transaction_count": live_data["transaction_count"],
            "total_inventory_value": Decimal(str(inv_val_query))
        }

    @classmethod
    def create_closing(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any],
        note: Optional[str] = None
    ) -> ClosingPeriod:
        """
        POST /closing-periods: Thực hiện chốt sổ.
        """
        period = PeriodService.resolve_period(**period_params)
        p_type = period["period_type"]
        p_start = period["period_start"]
        p_end = period["period_end"]
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        if p_type not in ["DAY", "MONTH", "QUARTER", "YEAR"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ hỗ trợ chốt sổ cho các kỳ: DAY, MONTH, QUARTER, YEAR."
            )

        # 1. Duplicate protection check
        existing = db.query(ClosingPeriod).filter(
            ClosingPeriod.user_id == user_id,
            ClosingPeriod.period_type == p_type,
            ClosingPeriod.period_start == p_start,
            ClosingPeriod.period_end == p_end
        ).first()

        if existing and existing.status == "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kỳ {p_type} từ ngày {p_start} đến {p_end} đã được chốt sổ trước đó (ID: {existing.closing_id}). Không thể chốt trùng."
            )

        # 1b. Không chốt kỳ cha khi còn kỳ con đã mở lại chưa chốt lại
        assert_no_reopened_children(db, user_id, p_type, p_start, p_end)

        # 2. Tính toán số liệu snapshot
        live_data = ReportService.get_live_report(db, user_id, period_params)
        summary = live_data["summary"]
        inv_val = Decimal("0.00")

        # 3. Tạo hoặc tái kích hoạt bản ghi ClosingPeriod
        if existing and existing.status == "OPEN":
            closing_period = existing
            closing_period.total_sales = summary["total_sales"]
            closing_period.total_purchase = summary["total_purchase"]
            closing_period.total_income = summary["total_income"]
            closing_period.total_expense = summary["total_expense"]
            closing_period.total_receivable = summary["total_receivable"]
            closing_period.total_payable = summary["total_payable"]
            closing_period.total_inventory_value = inv_val
            closing_period.status = "CLOSED"
            closing_period.note = note or existing.note
            closing_period.closed_at = datetime.now()
        else:
            closing_period = ClosingPeriod(
                user_id=user_id,
                period_type=p_type,
                period_start=p_start,
                period_end=p_end,
                total_sales=summary["total_sales"],
                total_purchase=summary["total_purchase"],
                total_income=summary["total_income"],
                total_expense=summary["total_expense"],
                total_receivable=summary["total_receivable"],
                total_payable=summary["total_payable"],
                total_inventory_value=inv_val,
                status="CLOSED",
                note=note,
                closed_at=datetime.now()
            )
            db.add(closing_period)

        db.flush()  # Lấy closing_id

        # 4. Tìm toàn bộ giao dịch trong kỳ và tạo ClosingTransaction
        tx_list = db.query(Transaction.transaction_id).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start_dt,
            Transaction.transaction_date <= end_dt
        ).all()

        # Xóa liên kết cũ nếu đang cập nhật kỳ mở lại
        db.query(ClosingTransaction).filter(
            ClosingTransaction.closing_id == closing_period.closing_id
        ).delete()

        closing_tx_records = [
            ClosingTransaction(
                closing_id=closing_period.closing_id,
                transaction_id=tx_id[0]
            )
            for tx_id in tx_list
        ]
        if closing_tx_records:
            db.bulk_save_objects(closing_tx_records)

        # 5. Luôn tự động gửi email báo cáo chốt sổ trực tiếp cho chính tài khoản người dùng
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản không tồn tại hoặc phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
            )

        recipient_email = getattr(user, "email", None)
        if recipient_email:
            try:
                report_log = ClosingReport(
                    closing_id=closing_period.closing_id,
                    user_id=user_id,
                    report_type="CLOSING_SUMMARY",
                    recipient_email=recipient_email,
                    send_status="PENDING"
                )
                db.add(report_log)
                db.flush()

                try:
                    ClosingEmailService._dispatch_closing_email(user, closing_period, summary, len(tx_list))
                    report_log.send_status = "SENT"
                    report_log.sent_at = datetime.now()
                    logger.info(f"Đã gửi email báo cáo chốt sổ thành công tới {recipient_email}")
                except Exception as e:
                    logger.error(f"Failed to send closing email report to {recipient_email}: {e}")
                    report_log.send_status = "FAILED"
                    report_log.error_message = str(e)
            except Exception as e_log:
                logger.error(f"Lỗi khi lưu/gửi báo cáo chốt sổ: {e_log}")

        db.commit()
        db.refresh(closing_period)

        # 6. Bắn WebSocket event CLOSING_COMPLETED và tạo Thông báo + Push FCM
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    ws_manager.notify_closing_event(
                        user_id=user_id,
                        event_name="CLOSING_COMPLETED",
                        data={
                            "closing_id": closing_period.closing_id,
                            "period_type": p_type,
                            "period_start": str(p_start),
                            "period_end": str(p_end),
                            "total_sales": float(summary["total_sales"]),
                            "total_income": float(summary["total_income"]),
                            "total_expense": float(summary["total_expense"]),
                            "transaction_count": len(tx_list)
                        }
                    )
                )
            except RuntimeError:
                pass
        except Exception as ws_err:
            logger.warning(f"Could not push WebSocket closing event: {ws_err}")

        # 7. Gửi thông báo hệ thống & Push FCM chốt sổ thành công
        try:
            from app.services.notification_service import NotificationService
            closing_time_str = datetime.now().strftime("%H:%M - %d/%m/%Y")
            NotificationService.create_notification({
                "userId": str(user_id),
                "title": f"Chốt sổ kỳ {p_type} thành công 🎉",
                "description": f"Sổ tài chính kỳ {p_type} ({p_start} đến {p_end}) đã được chốt hoàn tất lúc {closing_time_str}. Doanh thu: {int(summary['total_sales']):,}đ.",
                "notificationType": "CLOSING",
                "icon": "lock-clock",
                "iconColor": "#FFFFFF",
                "borderColor": "#0F766E",
                "isRead": False
            })
        except Exception as notif_err:
            logger.warning(f"Could not create closing notification: {notif_err}")

        return closing_period

    @classmethod
    def reclose_closing(
        cls,
        db: Session,
        user_id: int,
        closing_id: int
    ) -> ClosingPeriod:
        """
        POST /closing-periods/{id}/reclose:
        Chốt lại kỳ ĐÃ chốt để cập nhật snapshot với giao dịch phát sinh sau giờ chốt
        (vd đơn bán 22:30 khi lịch chốt lúc 22:00). Gửi lại email báo cáo với số mới.
        """
        closing = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == closing_id,
            ClosingPeriod.user_id == user_id
        ).first()
        if not closing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id} hoặc bạn không có quyền truy cập."
            )
        if closing.status != "CLOSED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kỳ này đang mở — hãy dùng Chốt sổ thay vì Chốt lại."
            )

        stamp = f"[Chốt lại lúc {datetime.now().strftime('%Y-%m-%d %H:%M')}: cập nhật giao dịch phát sinh sau giờ chốt]"
        note = f"{closing.note}\n{stamp}" if closing.note else stamp

        # create_closing chỉ cập nhật bản ghi đang OPEN → chuyển tạm về OPEN rồi chốt lại
        closing.status = "OPEN"
        db.flush()
        try:
            return cls.create_closing(db=db, user_id=user_id, period_params=period_params_of(closing), note=note)
        except Exception:
            db.rollback()
            raise

    @classmethod
    def reopen_closing(
        cls,
        db: Session,
        user_id: int,
        closing_id: int,
        reason: Optional[str] = None
    ) -> ClosingPeriod:
        """
        PATCH /closing-periods/{id}/reopen:
        Mở lại một kỳ đã chốt để bổ sung/sửa đổi giao dịch.
        """
        closing = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == closing_id,
            ClosingPeriod.user_id == user_id
        ).first()

        if not closing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id} hoặc bạn không có quyền truy cập."
            )

        if closing.status == "OPEN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kỳ chốt sổ này hiện đang ở trạng thái OPEN."
            )

        # Mở lại theo thứ bậc: kỳ cha đang chốt thì phải mở kỳ cha trước
        assert_can_reopen(db, closing)

        closing.status = "OPEN"
        append_note = f"[Reopened at {datetime.now().strftime('%Y-%m-%d %H:%M')}: {reason or 'Không có lý do'}]"
        closing.note = f"{closing.note}\n{append_note}" if closing.note else append_note

        db.commit()
        db.refresh(closing)
        return closing
