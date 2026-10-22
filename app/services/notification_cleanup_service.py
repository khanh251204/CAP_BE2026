import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.configs.firebase import db

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_RETENTION_DAYS = int(os.getenv("NOTIFICATION_RETENTION_DAYS", "14"))


class NotificationCleanupService:
    """
    Service dọn dẹp các thông báo Firestore quá hạn.
    Mặc định: xóa cứng các thông báo chưa đọc/chưa xem quá 14 ngày (2 tuần).
    """

    @staticmethod
    def cleanup_expired_notifications(retention_days: int = DEFAULT_NOTIFICATION_RETENTION_DAYS) -> Dict[str, Any]:
        """
        Quét và xóa cứng các thông báo thỏa mãn:
        - Thông báo cá nhân (userId != 'ALL'):
            createdAt < cutoff_time VÀ isRead == False
        - Thông báo chung (userId == 'ALL'):
            createdAt < cutoff_time VÀ (readByUsers rỗng hoặc đã quá hạn)
        """
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=retention_days)

        logger.info(
            f"[NotificationCleanup] Starting cleanup for notifications older than "
            f"{retention_days} days (cutoff: {cutoff_date.isoformat()})."
        )

        try:
            # Lấy toàn bộ notifications collection
            # Lưu ý: Do Firestore queries kết hợp inequal trên nhiều trường có thể cần composite index,
            # duyệt các doc có createdAt < cutoff_date và lọc điều kiện chưa đọc/chưa xem là tối ưu và an toàn nhất.
            docs_stream = (
                db.collection("notifications")
                .where("createdAt", "<", cutoff_date)
                .stream()
            )

            total_scanned = 0
            personal_deleted = 0
            global_deleted = 0
            batch = db.batch()
            batch_count = 0
            MAX_BATCH_SIZE = 450  # Giới hạn an toàn của Firestore batch là 500 operations

            for doc in docs_stream:
                total_scanned += 1
                data = doc.to_dict() or {}
                user_id = str(data.get("userId", ""))

                should_delete = False

                if user_id == "ALL":
                    # Thông báo ALL: nếu không có ai đọc hoặc đã quá hạn 14 ngày
                    read_by = data.get("readByUsers", [])
                    if not isinstance(read_by, list):
                        read_by = []
                    # Nếu chưa ai đọc (readByUsers rỗng) hoặc quá hạn retention_days
                    if len(read_by) == 0:
                        should_delete = True
                        global_deleted += 1
                else:
                    # Thông báo cá nhân: chưa đọc (isRead == False)
                    is_read = bool(data.get("isRead", False))
                    is_seen = bool(data.get("isSeen", False))
                    # Nếu cả chưa xem lẫn chưa đọc
                    if not is_read and not is_seen:
                        should_delete = True
                        personal_deleted += 1

                if should_delete:
                    batch.delete(doc.reference)
                    batch_count += 1

                    if batch_count >= MAX_BATCH_SIZE:
                        batch.commit()
                        batch = db.batch()
                        batch_count = 0

            # Commit batch còn lại nếu có
            if batch_count > 0:
                batch.commit()

            total_deleted = personal_deleted + global_deleted

            logger.info(
                f"[NotificationCleanup] Completed: scanned {total_scanned}, "
                f"deleted {total_deleted} (personal: {personal_deleted}, global: {global_deleted})."
            )

            return {
                "success": True,
                "retention_days": retention_days,
                "cutoff_date": cutoff_date.isoformat(),
                "total_scanned": total_scanned,
                "personal_deleted": personal_deleted,
                "global_deleted": global_deleted,
                "total_deleted": total_deleted,
                "message": f"Đã xóa thành công {total_deleted} thông báo chưa đọc quá {retention_days} ngày."
            }

        except Exception as exc:
            logger.error(f"[NotificationCleanup] Error during cleanup: {exc}", exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "retention_days": retention_days,
                "total_scanned": 0,
                "personal_deleted": 0,
                "global_deleted": 0,
                "total_deleted": 0,
                "message": f"Lỗi khi dọn dẹp thông báo: {str(exc)}"
            }


class NotificationCleanupScheduler:
    """
    Background Scheduler chạy định kỳ dọn dẹp các thông báo quá hạn trong Backend.
    Mặc định kiểm tra 1 lần mỗi ngày (86,400 giây).
    """

    _is_running = False
    _task = None
    _interval_seconds = int(os.getenv("NOTIFICATION_CLEANUP_INTERVAL_SECONDS", "86400"))  # 24 giờ

    @classmethod
    def start(cls):
        if cls._is_running:
            return
        cls._is_running = True
        cls._task = asyncio.create_task(cls._schedule_loop())
        logger.info(
            f"[NotificationCleanupScheduler] Started in background "
            f"(interval: {cls._interval_seconds}s, retention: {DEFAULT_NOTIFICATION_RETENTION_DAYS} days)."
        )

    @classmethod
    def stop(cls):
        cls._is_running = False
        if cls._task:
            cls._task.cancel()
        logger.info("[NotificationCleanupScheduler] Stopped.")

    @classmethod
    async def _schedule_loop(cls):
        # Chờ 30 giây đầu tiên sau khi server khởi động để hệ thống ổn định
        await asyncio.sleep(30)
        while cls._is_running:
            try:
                # Chạy dọn dẹp trong thread pool để tránh block event loop của FastAPI
                await asyncio.to_thread(
                    NotificationCleanupService.cleanup_expired_notifications,
                    DEFAULT_NOTIFICATION_RETENTION_DAYS
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[NotificationCleanupScheduler] Loop error: {e}", exc_info=True)

            try:
                await asyncio.sleep(cls._interval_seconds)
            except asyncio.CancelledError:
                break


def run_cleanup_job():
    """Hàm chạy trực tiếp từ CLI / Cron job hệ thống."""
    return NotificationCleanupService.cleanup_expired_notifications()


if __name__ == "__main__":
    result = run_cleanup_job()
    print("Notification Cleanup Result:", result)

