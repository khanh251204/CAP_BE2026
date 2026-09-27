import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import HTTPException, status

from app.models.closing_period_model import ClosingPeriod
from app.models.closing_transaction_model import ClosingTransaction
from app.models.closing_report_model import ClosingReport
from app.models.user_model import User
from app.services.websocket_manager import ws_manager
from app.services.closing.closing_email_service import ClosingEmailService

logger = logging.getLogger(__name__)


class ClosingReportQueryService:
    @classmethod
    def get_closing_reports(
        cls,
        db: Session,
        user_id: int,
        closing_id: Optional[int] = None,
        status_val: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        GET /closing-reports: Lịch sử gửi báo cáo qua email.
        """
        query = db.query(ClosingReport).filter(ClosingReport.user_id == user_id)
        if closing_id:
            query = query.filter(ClosingReport.closing_id == closing_id)
        if status_val:
            query = query.filter(ClosingReport.send_status == status_val.upper())

        rows = query.order_by(desc(ClosingReport.created_at)).all()
        return [{
            "report_id": r.report_id,
            "closing_id": r.closing_id,
            "user_id": r.user_id,
            "report_type": r.report_type,
            "recipient_email": r.recipient_email,
            "send_status": r.send_status,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else ""
        } for r in rows]

    @classmethod
    def resend_closing_report(
        cls,
        db: Session,
        user_id: int,
        report_id: int
    ) -> Dict[str, Any]:
        """
        POST /closing-reports/{id}/resend: Gửi lại báo cáo email.
        """
        report_log = db.query(ClosingReport).filter(
            ClosingReport.report_id == report_id,
            ClosingReport.user_id == user_id
        ).first()

        if not report_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy bản ghi gửi báo cáo ID {report_id}."
            )

        closing = db.query(ClosingPeriod).filter(ClosingPeriod.closing_id == report_log.closing_id).first()
        user = db.query(User).filter(User.user_id == user_id).first()

        summary = {
            "total_sales": closing.total_sales,
            "total_purchase": closing.total_purchase,
            "total_income": closing.total_income,
            "total_expense": closing.total_expense,
            "total_receivable": closing.total_receivable,
            "total_payable": closing.total_payable
        }

        tx_count = db.query(func.count(ClosingTransaction.transaction_id)).filter(
            ClosingTransaction.closing_id == closing.closing_id
        ).scalar() or 0

        try:
            ClosingEmailService._dispatch_closing_email(user, closing, summary, tx_count)
            report_log.send_status = "SENT"
            report_log.sent_at = datetime.now()
            report_log.error_message = None
            db.commit()
            db.refresh(report_log)

            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    ws_manager.notify_closing_event(
                        user_id=user_id,
                        event_name="CLOSING_REPORT_SENT",
                        data={"report_id": report_id, "recipient": report_log.recipient_email}
                    )
                )
            except RuntimeError:
                pass

            return {
                "message": f"Đã gửi lại báo cáo tới {report_log.recipient_email} thành công!",
                "report_id": report_id,
                "status": "SENT"
            }
        except Exception as e:
            logger.error(f"Failed to resend closing report: {e}")
            report_log.send_status = "FAILED"
            report_log.error_message = str(e)
            db.commit()

            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    ws_manager.notify_closing_event(
                        user_id=user_id,
                        event_name="CLOSING_REPORT_FAILED",
                        data={"report_id": report_id, "error": str(e)}
                    )
                )
            except RuntimeError:
                pass

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể gửi email báo cáo: {str(e)}"
            )
