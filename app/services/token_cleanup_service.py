import os
import asyncio
import logging
from datetime import datetime

from app.configs.database import get_db_session
from app.services.refresh_token_service import purge_expired_refresh_tokens

logger = logging.getLogger(__name__)


class TokenCleanupScheduler:
    """
    Background Scheduler tự động quét và xóa cứng các Refresh Token
    đã hết hạn hoặc đã thu hồi (is_revoked=True) trong cơ sở dữ liệu.
    Mặc định chạy 1 lần mỗi 24 giờ.
    """

    _is_running = False
    _task = None
    _interval_seconds = int(os.getenv("TOKEN_CLEANUP_INTERVAL_SECONDS", "86400"))  # 24h

    @classmethod
    def start(cls):
        if cls._is_running:
            return
        cls._is_running = True
        cls._task = asyncio.create_task(cls._schedule_loop())
        logger.info(f"[TokenCleanupScheduler] Started in background (interval: {cls._interval_seconds}s).")

    @classmethod
    def stop(cls):
        cls._is_running = False
        if cls._task:
            cls._task.cancel()
        logger.info("[TokenCleanupScheduler] Stopped.")

    @classmethod
    def run_cleanup(cls) -> int:
        """Hàm dọn dẹp trực tiếp."""
        db = get_db_session()
        try:
            deleted_count = purge_expired_refresh_tokens(db)
            db.commit()
            if deleted_count > 0:
                logger.info(f"[TokenCleanup] Đã xóa cứng {deleted_count} refresh token hết hạn/thu hồi.")
            return deleted_count
        except Exception as e:
            db.rollback()
            logger.error(f"[TokenCleanup] Lỗi dọn dẹp refresh token: {e}", exc_info=True)
            return 0
        finally:
            db.close()

    @classmethod
    async def _schedule_loop(cls):
        # Chờ 15s sau khi server khởi động rồi dọn dẹp 1 lần
        await asyncio.sleep(15)
        while cls._is_running:
            try:
                await asyncio.to_thread(cls.run_cleanup)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TokenCleanupScheduler] Loop error: {e}", exc_info=True)

            try:
                await asyncio.sleep(cls._interval_seconds)
            except asyncio.CancelledError:
                break
