import asyncio
import logging
from datetime import datetime, time, date
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.models.closing_setting_model import ClosingSetting
from app.models.closing_period_model import ClosingPeriod
from app.services.closing_service import ClosingService
from app.services.period_service import PeriodService
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class ClosingScheduler:
    """
    Background Scheduler kiểm tra và thực thi lịch tự động chốt sổ.
    Chạy độc lập trên Backend.
    """

    _is_running = False
    _task = None

    @classmethod
    def start(cls):
        if cls._is_running:
            return
        cls._is_running = True
        cls._task = asyncio.create_task(cls._schedule_loop())
        logger.info("ClosingScheduler started in background.")

    @classmethod
    def stop(cls):
        cls._is_running = False
        if cls._task:
            cls._task.cancel()
        logger.info("ClosingScheduler stopped.")

    @classmethod
    async def _schedule_loop(cls):
        """
        Vòng lặp kiểm tra mỗi 60 giây.
        """
        while cls._is_running:
            try:
                await cls.check_and_execute_closing()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ClosingScheduler loop: {e}", exc_info=True)
            
            # Chờ 60 giây cho lần kiểm tra tiếp theo
            await asyncio.sleep(60)

    @classmethod
    async def check_and_execute_closing(cls):
        """
        Kiểm tra tất cả setting đang kích hoạt của các User và so sánh với giờ hiện tại.
        """
        db = get_db_session()
        try:
            active_settings = db.query(ClosingSetting).filter(
                ClosingSetting.is_active == True
            ).all()

            for setting in active_settings:
                try:
                    await cls._process_user_setting(db, setting)
                except Exception as user_err:
                    logger.error(f"Error processing closing for user {setting.user_id}: {user_err}")
        finally:
            db.close()

    @classmethod
    async def _process_user_setting(cls, db: Session, setting: ClosingSetting):
        tz = PeriodService.get_tz(setting.timezone)
        now = datetime.now(tz)

        # So sánh giờ và phút
        if now.hour != setting.closing_time.hour or now.minute != setting.closing_time.minute:
            return

        p_type = setting.period_type
        period_params = {"period_type": p_type, "tz_str": setting.timezone}

        if p_type == "DAY":
            period_params["date_val"] = now.date()
        elif p_type == "MONTH":
            period_params["year"] = now.year
            period_params["month"] = now.month
        elif p_type == "QUARTER":
            period_params["year"] = now.year
            period_params["quarter"] = (now.month - 1) // 3 + 1
        elif p_type == "YEAR":
            period_params["year"] = now.year

        period = PeriodService.resolve_period(**period_params)

        # Tháng / quý / năm: chỉ chốt vào NGÀY CUỐI KỲ (đúng giờ người dùng đặt).
        # Trước đây chạy mỗi ngày → ngày 1/10 đã chốt cả tháng 10 khi tháng chưa kết thúc.
        if p_type != "DAY" and now.date() != period["period_end"]:
            return

        # Kiểm tra xem kỳ này đã chốt chưa
        existing = db.query(ClosingPeriod).filter(
            ClosingPeriod.user_id == setting.user_id,
            ClosingPeriod.period_type == p_type,
            ClosingPeriod.period_start == period["period_start"],
            ClosingPeriod.period_end == period["period_end"],
            ClosingPeriod.status == "CLOSED"
        ).first()

        if existing:
            return  # Đã chốt rồi, không làm lại

        if setting.auto_close:
            logger.info(f"Auto-closing period {p_type} for user {setting.user_id}...")
            ClosingService.create_closing(
                db=db,
                user_id=setting.user_id,
                period_params=period_params,
                note=f"Tự động chốt theo lịch {setting.closing_time.strftime('%H:%M')}"
            )
        else:
            # Gửi yêu cầu xác nhận qua WebSocket
            preview = ClosingService.preview_closing(
                db=db,
                user_id=setting.user_id,
                period_params=period_params
            )
            await ws_manager.notify_closing_event(
                user_id=setting.user_id,
                event_name="CLOSING_CONFIRMATION_REQUIRED",
                data={
                    "period_type": p_type,
                    "period_start": str(period["period_start"]),
                    "period_end": str(period["period_end"]),
                    "summary": {
                        "total_sales": float(preview["summary"]["total_sales"]),
                        "total_income": float(preview["summary"]["total_income"]),
                        "total_expense": float(preview["summary"]["total_expense"]),
                        "total_receivable": float(preview["summary"]["total_receivable"]),
                        "total_payable": float(preview["summary"]["total_payable"])
                    },
                    "transaction_count": preview["transaction_count"],
                    "message": f"Đã đến giờ chốt sổ kỳ {p_type}. Vui lòng kiểm tra và xác nhận chốt sổ."
                }
            )
            # Gửi thông báo in-app và Push FCM nhắc nhở người dùng chốt sổ
            try:
                from app.services.notification_service import NotificationService
                NotificationService.create_notification({
                    "userId": str(setting.user_id),
                    "title": f"Nhắc nhở chốt sổ kỳ {p_type} ⏰",
                    "description": f"Đã đến khung giờ chốt sổ ({setting.closing_time.strftime('%H:%M')}). Bạn có {preview['transaction_count']} giao dịch cần kiểm tra và xác nhận.",
                    "notificationType": "CLOSING_REMINDER",
                    "icon": "clock-alert-outline",
                    "iconColor": "#FFFFFF",
                    "borderColor": "#F59E0B",
                    "isRead": False
                })
            except Exception as ne:
                logger.warning(f"Could not create closing reminder notification: {ne}")

