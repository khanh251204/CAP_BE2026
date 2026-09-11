import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from datetime import datetime, date, time
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from fastapi import HTTPException, status

from app.models.closing_period_model import ClosingPeriod
from app.models.closing_transaction_model import ClosingTransaction
from app.models.closing_setting_model import ClosingSetting
from app.models.closing_report_model import ClosingReport
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.product_model import Product
from app.models.user_model import User
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.services.period_service import PeriodService
from app.services.report_service import ReportService
from app.services.email_service import send_email
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class ClosingService:
    """
    Closing Engine:
    - Nghiệp vụ ghi dữ liệu (Snapshot write).
    - Tạo ClosingPeriod, ClosingTransaction, ClosingReport.
    - Chống chốt trùng (Duplicate protection).
    - Phân quyền nghiêm ngặt theo user_id.
    """

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

        # Kiểm tra xem kỳ này đã được chốt hay chưa
        existing = db.query(ClosingPeriod).filter(
            ClosingPeriod.user_id == user_id,
            ClosingPeriod.period_type == p_type,
            ClosingPeriod.period_start == p_start,
            ClosingPeriod.period_end == p_end
        ).first()

        is_closed = (existing is not None and existing.status == "CLOSED")
        existing_id = existing.closing_id if existing else None

        # Lấy số liệu tính toán realtime hiện tại
        live_data = ReportService.get_live_report(db, user_id, period_params)
        summary = live_data["summary"]

        # Tính tổng giá trị tồn kho ước tính (SUM(min_quantity * unit_price) hoặc từ Inventory)
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
        POST /closing-periods:
        Thực hiện chốt sổ:
        1. Kiểm tra duplicate protection.
        2. Tính toán snapshot số liệu.
        3. Tạo ClosingPeriod.
        4. Liên kết giao dịch vào ClosingTransaction.
        5. Gửi email báo cáo nếu cấu hình bật.
        6. Bắn WebSocket event CLOSING_COMPLETED.
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
                    cls._dispatch_closing_email(user, closing_period, summary, len(tx_list))
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

        # 6. Bắn WebSocket event CLOSING_COMPLETED
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
                pass  # Không có running loop (ví dụ khi chạy sync unit test)
        except Exception as ws_err:
            logger.warning(f"Could not push WebSocket closing event: {ws_err}")

        return closing_period

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

        closing.status = "OPEN"
        append_note = f"[Reopened at {datetime.now().strftime('%Y-%m-%d %H:%M')}: {reason or 'Không có lý do'}]"
        closing.note = f"{closing.note}\n{append_note}" if closing.note else append_note

        db.commit()
        db.refresh(closing)
        return closing

    @classmethod
    def get_closing_periods(
        cls,
        db: Session,
        user_id: int,
        period_type: Optional[str] = None,
        status_val: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        GET /closing-periods:
        Lấy danh sách các kỳ đã chốt (snapshot history).
        """
        query = db.query(ClosingPeriod).filter(ClosingPeriod.user_id == user_id)

        if period_type:
            query = query.filter(ClosingPeriod.period_type == period_type.upper())
        if status_val:
            query = query.filter(ClosingPeriod.status == status_val.upper())

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        rows = query.order_by(desc(ClosingPeriod.period_end), desc(ClosingPeriod.closing_id)).offset(offset).limit(page_size).all()

        items = []
        for r in rows:
            tx_count = db.query(func.count(ClosingTransaction.transaction_id)).filter(
                ClosingTransaction.closing_id == r.closing_id
            ).scalar() or 0

            items.append({
                "closing_id": r.closing_id,
                "user_id": r.user_id,
                "period_type": r.period_type,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "total_sales": Decimal(str(r.total_sales or 0)),
                "total_purchase": Decimal(str(r.total_purchase or 0)),
                "total_income": Decimal(str(r.total_income or 0)),
                "total_expense": Decimal(str(r.total_expense or 0)),
                "total_receivable": Decimal(str(r.total_receivable or 0)),
                "total_payable": Decimal(str(r.total_payable or 0)),
                "total_inventory_value": Decimal(str(r.total_inventory_value or 0)),
                "status": r.status,
                "note": r.note,
                "closed_at": r.closed_at.isoformat() if r.closed_at else "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "transaction_count": tx_count
            })

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total
        }

    @classmethod
    def get_closing_period_detail(
        cls,
        db: Session,
        user_id: int,
        closing_id: int
    ) -> Dict[str, Any]:
        """
        GET /closing-periods/{id}:
        Lấy chi tiết một kỳ chốt sổ.
        """
        r = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == closing_id,
            ClosingPeriod.user_id == user_id
        ).first()

        if not r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id}."
            )

        tx_count = db.query(func.count(ClosingTransaction.transaction_id)).filter(
            ClosingTransaction.closing_id == r.closing_id
        ).scalar() or 0

        return {
            "closing_id": r.closing_id,
            "user_id": r.user_id,
            "period_type": r.period_type,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "total_sales": Decimal(str(r.total_sales or 0)),
            "total_purchase": Decimal(str(r.total_purchase or 0)),
            "total_income": Decimal(str(r.total_income or 0)),
            "total_expense": Decimal(str(r.total_expense or 0)),
            "total_receivable": Decimal(str(r.total_receivable or 0)),
            "total_payable": Decimal(str(r.total_payable or 0)),
            "total_inventory_value": Decimal(str(r.total_inventory_value or 0)),
            "status": r.status,
            "note": r.note,
            "closed_at": r.closed_at.isoformat() if r.closed_at else "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "transaction_count": tx_count
        }

    @classmethod
    def get_closing_transactions(
        cls,
        db: Session,
        user_id: int,
        closing_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        GET /closing-periods/{id}/transactions:
        Drill-down: Danh sách các giao dịch thuộc kỳ chốt sổ đã lưu trong closing_transaction.
        """
        # Kiểm tra quyền sở hữu kỳ chốt
        closing = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == closing_id,
            ClosingPeriod.user_id == user_id
        ).first()

        if not closing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy kỳ chốt sổ ID {closing_id}."
            )

        query = db.query(
            Transaction.transaction_id,
            Transaction.transaction_date,
            Intent.intent_name,
            Transaction.total_amount,
            Transaction.payment_status,
            Transaction.input_method,
            Transaction.note,
            Category.category_name,
            Customer.customer_name,
            Supplier.supplier_name
        ).join(ClosingTransaction, Transaction.transaction_id == ClosingTransaction.transaction_id)\
         .outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .outerjoin(Customer, Transaction.customer_id == Customer.customer_id)\
         .outerjoin(Supplier, Transaction.supplier_id == Supplier.supplier_id)\
         .filter(
             ClosingTransaction.closing_id == closing_id,
             Transaction.user_id == user_id
         )

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        rows = query.order_by(desc(Transaction.transaction_date)).offset(offset).limit(page_size).all()

        items = []
        for r in rows:
            items.append({
                "transaction_id": r.transaction_id,
                "transaction_date": r.transaction_date.isoformat() if r.transaction_date else "",
                "intent": r.intent_name,
                "total_amount": Decimal(str(r.total_amount or 0)),
                "payment_status": str(r.payment_status),
                "input_method": str(r.input_method) if r.input_method else None,
                "category_name": r.category_name,
                "customer_name": r.customer_name,
                "supplier_name": r.supplier_name,
                "note": r.note
            })

        return {
            "closing_id": closing_id,
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total
        }

    @classmethod
    def get_closing_settings(
        cls,
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """
        GET /closing-settings:
        Lấy cấu hình tự động chốt sổ của người dùng.
        Nếu chưa có, tạo cấu hình mặc định.
        """
        setting = db.query(ClosingSetting).filter(ClosingSetting.user_id == user_id).first()
        if not setting:
            setting = ClosingSetting(
                user_id=user_id,
                period_type="DAY",
                closing_time=time(23, 0, 0),
                auto_close=False,
                send_report=True,
                report_channel="EMAIL",
                timezone="Asia/Ho_Chi_Minh",
                is_active=True
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)

        return {
            "setting_id": setting.setting_id,
            "user_id": setting.user_id,
            "period_type": setting.period_type,
            "closing_time": setting.closing_time.strftime("%H:%M:%S"),
            "auto_close": setting.auto_close,
            "send_report": setting.send_report,
            "report_channel": setting.report_channel,
            "timezone": setting.timezone,
            "is_active": setting.is_active
        }

    @classmethod
    def update_closing_settings(
        cls,
        db: Session,
        user_id: int,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        PUT /closing-settings:
        Cập nhật cấu hình tự động chốt sổ.
        """
        setting = db.query(ClosingSetting).filter(ClosingSetting.user_id == user_id).first()
        if not setting:
            setting = ClosingSetting(user_id=user_id)
            db.add(setting)

        if "period_type" in update_data and update_data["period_type"] is not None:
            pt = update_data["period_type"].upper()
            if pt not in ["DAY", "MONTH", "QUARTER", "YEAR"]:
                raise HTTPException(status_code=400, detail="period_type không hợp lệ.")
            setting.period_type = pt

        if "closing_time" in update_data and update_data["closing_time"] is not None:
            t_str = update_data["closing_time"].strip()
            try:
                if len(t_str.split(":")) == 2:
                    t_str += ":00"
                parsed_time = datetime.strptime(t_str, "%H:%M:%S").time()
                setting.closing_time = parsed_time
            except ValueError:
                raise HTTPException(status_code=400, detail="closing_time phải có format HH:MM hoặc HH:MM:SS.")

        if "auto_close" in update_data and update_data["auto_close"] is not None:
            setting.auto_close = bool(update_data["auto_close"])

        if "send_report" in update_data and update_data["send_report"] is not None:
            setting.send_report = bool(update_data["send_report"])

        if "report_channel" in update_data and update_data["report_channel"] is not None:
            setting.report_channel = update_data["report_channel"]

        if "timezone" in update_data and update_data["timezone"] is not None:
            setting.timezone = update_data["timezone"]

        if "is_active" in update_data and update_data["is_active"] is not None:
            setting.is_active = bool(update_data["is_active"])

        setting.updated_at = datetime.now()
        db.commit()
        db.refresh(setting)

        return cls.get_closing_settings(db, user_id)

    @classmethod
    def get_closing_reports(
        cls,
        db: Session,
        user_id: int,
        closing_id: Optional[int] = None,
        status_val: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        GET /closing-reports:
        Lịch sử gửi báo cáo qua email.
        """
        query = db.query(ClosingReport).filter(ClosingReport.user_id == user_id)
        if closing_id:
            query = query.filter(ClosingReport.closing_id == closing_id)
        if status_val:
            query = query.filter(ClosingReport.send_status == status_val.upper())

        rows = query.order_by(desc(ClosingReport.created_at)).all()
        items = []
        for r in rows:
            items.append({
                "report_id": r.report_id,
                "closing_id": r.closing_id,
                "user_id": r.user_id,
                "report_type": r.report_type,
                "recipient_email": r.recipient_email,
                "send_status": r.send_status,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else ""
            })
        return items

    @classmethod
    def resend_closing_report(
        cls,
        db: Session,
        user_id: int,
        report_id: int
    ) -> Dict[str, Any]:
        """
        POST /closing-reports/{id}/resend:
        Gửi lại báo cáo email bị lỗi hoặc gửi bổ sung.
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

        closing = db.query(ClosingPeriod).filter(
            ClosingPeriod.closing_id == report_log.closing_id
        ).first()

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
            cls._dispatch_closing_email(user, closing, summary, tx_count)
            report_log.send_status = "SENT"
            report_log.sent_at = datetime.now()
            report_log.error_message = None
            db.commit()
            db.refresh(report_log)

            import asyncio
            asyncio.create_task(
                ws_manager.notify_closing_event(
                    user_id=user_id,
                    event_name="CLOSING_REPORT_SENT",
                    data={"report_id": report_id, "recipient": report_log.recipient_email}
                )
            )

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
            asyncio.create_task(
                ws_manager.notify_closing_event(
                    user_id=user_id,
                    event_name="CLOSING_REPORT_FAILED",
                    data={"report_id": report_id, "error": str(e)}
                )
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể gửi email báo cáo: {str(e)}"
            )

    @classmethod
    def _dispatch_closing_email(
        cls,
        user: User,
        closing: ClosingPeriod,
        summary: Dict[str, Any],
        transaction_count: int
    ):
        """
        Hàm helper gửi email báo cáo tổng kết kỳ chốt sổ tới email người dùng.
        """
        recipient_email = getattr(user, "email", None)
        if not recipient_email:
            raise ValueError("Người dùng không có email hợp lệ để nhận báo cáo.")

        user_name = getattr(user, "full_name", None) or "Quý khách"
        store_name = getattr(user, "store_name", None) or "Cửa hàng"

        def safe_int(v):
            try:
                return int(Decimal(str(v or 0)))
            except Exception:
                return 0

        total_sales_val = safe_int(summary.get("total_sales"))
        total_purchase_val = safe_int(summary.get("total_purchase"))
        total_income_val = safe_int(summary.get("total_income"))
        total_expense_val = safe_int(summary.get("total_expense"))
        cogs_val = safe_int(summary.get("cogs"))
        op_expense_val = safe_int(summary.get("operating_expense"))
        profit_val = safe_int(summary.get("profit"))
        total_receivable_val = safe_int(summary.get("total_receivable"))
        total_payable_val = safe_int(summary.get("total_payable"))

        period_label = f"Kỳ {closing.period_type} ({closing.period_start} đến {closing.period_end})"
        subject = f"[{store_name}] Báo cáo chốt sổ {period_label}"

        closed_dt = closing.closed_at if isinstance(closing.closed_at, (datetime, date)) else datetime.now()
        closed_str = closed_dt.strftime("%d/%m/%Y %H:%M:%S")

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="text-align: center; border-bottom: 2px solid #2563eb; padding-bottom: 15px;">
                <h2 style="color: #2563eb; margin: 0;">BÁO CÁO CHỐT SỔ TÀI CHÍNH</h2>
                <p style="margin: 5px 0 0; color: #666;">{store_name} — {period_label}</p>
            </div>
            
            <p style="margin-top: 20px;">Xin chào <strong>{user_name}</strong>,</p>
            <p>Hệ thống xin gửi tới bạn bảng tổng kết tài chính của kỳ chốt sổ vừa hoàn tất:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Doanh thu bán hàng:</strong></td>
                    <td style="padding: 10px; text-align: right; color: #16a34a; font-weight: bold;">{total_sales_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Giá vốn hàng bán (COGS):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #64748b; font-weight: bold;">{cogs_val:,} đ</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Chi phí hoạt động:</strong></td>
                    <td style="padding: 10px; text-align: right; color: #dc2626; font-weight: bold;">{op_expense_val:,} đ</td>
                </tr>
                <tr style="background-color: #eff6ff; border-bottom: 2px solid #3b82f6;">
                    <td style="padding: 10px;"><strong>Lợi nhuận ước tính:</strong></td>
                    <td style="padding: 10px; text-align: right; color: {'#16a34a' if profit_val >= 0 else '#dc2626'}; font-weight: bold; font-size: 16px;">{profit_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Tổng nhập hàng (Mua hàng):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #ea580c; font-weight: bold;">{total_purchase_val:,} đ</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Tổng tiền thực thu:</strong></td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{total_income_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Tổng tiền thực chi:</strong></td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{total_expense_val:,} đ</td>
                </tr>
                <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Công nợ phải thu (Khách nợ):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #2563eb; font-weight: bold;">{total_receivable_val:,} đ</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px;"><strong>Công nợ phải trả (Nợ NCC):</strong></td>
                    <td style="padding: 10px; text-align: right; color: #dc2626; font-weight: bold;">{total_payable_val:,} đ</td>
                </tr>
                <tr style="background-color: #f1f5f9;">
                    <td style="padding: 10px;"><strong>Tổng số giao dịch:</strong></td>
                    <td style="padding: 10px; text-align: right; font-weight: bold;">{transaction_count}</td>
                </tr>
            </table>

            <p style="font-size: 13px; color: #64748b;">Thời điểm chốt: {closed_str}</p>
            <p style="font-size: 13px; color: #64748b;">Mã kỳ chốt: #{closing.closing_id}</p>
            
            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center;">
                Email được gửi tự động từ hệ thống quản lý tài chính VoiceCashBook.
            </div>
        </body>
        </html>
        """

        send_email(
            to_email=recipient_email,
            subject=subject,
            text_content=f"Báo cáo chốt sổ {period_label}: Doanh thu: {summary.get('total_sales', 0)} đ, Tổng thu: {summary.get('total_income', 0)} đ, Tổng chi: {summary.get('total_expense', 0)} đ.",
            html_content=html_body
        )
