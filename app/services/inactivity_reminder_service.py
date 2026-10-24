import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.configs.firebase import db as firestore_db
from app.models.user_model import User
from app.models.refresh_token_model import RefreshToken
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

DEFAULT_INACTIVITY_DAYS = int(os.getenv("INACTIVITY_REMINDER_DAYS", "7"))
DEFAULT_INTERVAL_SECONDS = int(os.getenv("INACTIVITY_REMINDER_INTERVAL_SECONDS", "86400"))  # 24 giờ


class InactivityReminderService:
    """
    Dịch vụ kiểm tra và gửi Push Notification qua FCM (kèm lưu Firestore)
    cho những người dùng không đăng nhập/vào app trong vòng 7 ngày (hoặc số ngày cấu hình).
    """

    @classmethod
    def get_user_last_active(cls, db: Session, user: User) -> datetime:
        """
        Xác định thời điểm hoạt động / đăng nhập gần nhất của User:
        1. Firestore `user_activity.lastLoginAt` (nếu có).
        2. MySQL `Refresh_Token` mới nhất (thời điểm login / rotate token gần nhất).
        3. MySQL `User.created_at` (thời điểm đăng ký tài khoản).
        Lấy giá trị lớn nhất trong các mốc trên.
        """
        candidates: List[datetime] = []

        # 1. Từ Firestore user_activity
        try:
            doc = firestore_db.collection("user_activity").document(str(user.user_id)).get()
            if doc.exists:
                data = doc.to_dict() or {}
                last_login_at = data.get("lastLoginAt")
                if last_login_at:
                    if hasattr(last_login_at, "to_datetime"):
                        candidates.append(last_login_at.to_datetime())
                    elif isinstance(last_login_at, datetime):
                        candidates.append(last_login_at)
        except Exception as e:
            logger.debug(f"[InactivityReminder] Lỗi đọc user_activity của user {user.user_id}: {e}")

        # 2. Từ MySQL Refresh_Token mới nhất
        try:
            latest_token = (
                db.query(RefreshToken)
                .filter(RefreshToken.user_id == user.user_id)
                .order_by(RefreshToken.created_at.desc())
                .first()
            )
            if latest_token and latest_token.created_at:
                candidates.append(latest_token.created_at)
        except Exception as e:
            logger.debug(f"[InactivityReminder] Lỗi đọc refresh_token của user {user.user_id}: {e}")

        # 3. Fallback: ngày tạo user
        if user.created_at:
            candidates.append(user.created_at)

        if not candidates:
            return datetime.now(timezone.utc)

        # Chuẩn hóa về timezone-aware (UTC) để so sánh
        normalized: List[datetime] = []
        for dt in candidates:
            if dt.tzinfo is None:
                normalized.append(dt.replace(tzinfo=timezone.utc))
            else:
                normalized.append(dt.astimezone(timezone.utc))

        return max(normalized)

    @classmethod
    def has_recent_inactivity_reminder(cls, user_id: int | str, cooldown_days: int = 7) -> bool:
        """
        Kiểm tra xem User đã nhận thông báo nhắc nhở vắng mặt trong vòng cooldown_days ngày qua chưa.
        Tránh spam người dùng mỗi ngày sau khi đã đủ 7 ngày vắng mặt.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        try:
            # 1. Kiểm tra nhanh qua document user_activity
            doc = firestore_db.collection("user_activity").document(str(user_id)).get()
            if doc.exists:
                data = doc.to_dict() or {}
                last_notif_at = data.get("lastInactivityNotificationAt")
                if last_notif_at:
                    dt = last_notif_at.to_datetime() if hasattr(last_notif_at, "to_datetime") else last_notif_at
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    if dt >= cutoff:
                        return True

            # 2. Kiểm tra trong collection notifications
            notif_docs = (
                firestore_db.collection("notifications")
                .where("userId", "==", str(user_id))
                .where("notificationType", "==", "INACTIVITY_REMINDER")
                .stream()
            )
            for ndoc in notif_docs:
                ndata = ndoc.to_dict() or {}
                created_at = ndata.get("createdAt")
                if created_at:
                    dt = created_at.to_datetime() if hasattr(created_at, "to_datetime") else created_at
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    if dt >= cutoff:
                        return True

            return False
        except Exception as e:
            logger.warning(f"[InactivityReminder] Lỗi kiểm tra cooldown thông báo cho user {user_id}: {e}")
            return False

    @classmethod
    def check_and_notify_inactive_users(
        cls,
        db: Session,
        inactive_days: int = DEFAULT_INACTIVITY_DAYS
    ) -> Dict[str, Any]:
        """
        Quét tất cả người dùng hợp lệ và gửi thông báo nếu đã >= inactive_days ngày không hoạt động.
        """
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=inactive_days)

        try:
            # Chỉ gửi cho user đã xác thực email
            users = db.query(User).filter(User.is_verified == True).all()
        except Exception as e:
            logger.error(f"[InactivityReminder] Không thể query danh sách User: {e}")
            return {"scanned": 0, "notified": 0, "error": str(e)}

        scanned_count = len(users)
        notified_count = 0

        for user in users:
            try:
                last_active = cls.get_user_last_active(db, user)
                inactive_duration = now - last_active

                if inactive_duration >= threshold:
                    # Kiểm tra cooldown để không bắn liên tục
                    if cls.has_recent_inactivity_reminder(user.user_id, cooldown_days=inactive_days):
                        continue

                    display_name = user.full_name or "bạn"
                    title = "Bạn ơi, đã 1 tuần rồi chưa ghi chép sổ sách! 📊"
                    description = (
                        f"Chào {display_name}, đã hơn {inactive_days} ngày bạn chưa vào VoiceCashBook. "
                        "Hãy dành chút thời gian ghi chép lại các khoản thu chi để quản lý tài chính thật tốt nhé!"
                    )

                    # Gửi thông báo (tự động lưu Firestore notifications + đẩy FCM push)
                    NotificationService.create_notification({
                        "userId": str(user.user_id),
                        "title": title,
                        "description": description,
                        "icon": "calendar",
                        "iconColor": "#FFFFFF",
                        "borderColor": "#3B82F6",
                        "notificationType": "INACTIVITY_REMINDER",
                        "isRead": False
                    })

                    # Cập nhật thời điểm vừa gửi thông báo vào user_activity
                    try:
                        from firebase_admin import firestore
                        firestore_db.collection("user_activity").document(str(user.user_id)).set({
                            "userId": str(user.user_id),
                            "lastInactivityNotificationAt": firestore.SERVER_TIMESTAMP
                        }, merge=True)
                    except Exception:
                        pass

                    notified_count += 1
                    logger.info(
                        f"[InactivityReminder] Đã gửi thông báo nhắc nhở 1 tuần không vào app cho user {user.user_id} ({user.email})"
                    )

            except Exception as e:
                logger.warning(f"[InactivityReminder] Lỗi xử lý cho user {user.user_id}: {e}")

        logger.info(
            f"[InactivityReminder] Hoàn tất quét: {notified_count}/{scanned_count} người dùng được nhắc nhở vắng mặt."
        )
        return {
            "scanned": scanned_count,
            "notified": notified_count
        }


class InactivityReminderScheduler:
    """
    Background Scheduler định kỳ chạy 1 lần/ngày kiểm tra người dùng không vào app 7 ngày.
    """

    _is_running = False
    _task = None
    _interval_seconds = DEFAULT_INTERVAL_SECONDS

    @classmethod
    def start(cls):
        if cls._is_running:
            return
        cls._is_running = True
        cls._task = asyncio.create_task(cls._schedule_loop())
        logger.info(
            f"[InactivityReminderScheduler] Started in background (interval: {cls._interval_seconds}s, inactive_days: {DEFAULT_INACTIVITY_DAYS})."
        )

    @classmethod
    def stop(cls):
        cls._is_running = False
        if cls._task:
            cls._task.cancel()
        logger.info("[InactivityReminderScheduler] Stopped.")

    @classmethod
    async def _schedule_loop(cls):
        # Chờ 60 giây đầu sau khi server khởi động để hệ thống ổn định
        await asyncio.sleep(60)
        while cls._is_running:
            try:
                await cls._execute_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[InactivityReminderScheduler] Loop error: {e}", exc_info=True)

            try:
                await asyncio.sleep(cls._interval_seconds)
            except asyncio.CancelledError:
                break

    @classmethod
    async def _execute_check(cls):
        def _job():
            with get_db_session() as db:
                return InactivityReminderService.check_and_notify_inactive_users(
                    db=db,
                    inactive_days=DEFAULT_INACTIVITY_DAYS
                )

        await asyncio.to_thread(_job)
