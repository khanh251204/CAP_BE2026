import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.models.system_log_model import SystemLog, SystemLogLevel

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = int(os.getenv("SYSTEM_LOGS_RETENTION_DAYS", "30"))
DEFAULT_ERROR_RETENTION_DAYS = int(os.getenv("SYSTEM_LOGS_ERROR_RETENTION_DAYS", "90"))


def cleanup_expired_system_logs(
    db: Session,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    error_retention_days: int = DEFAULT_ERROR_RETENTION_DAYS
) -> Dict[str, Any]:
    """
    Dọn dẹp logs theo chính sách lưu trữ (data retention policy):
    - Xóa logs INFO và WARNING cũ hơn `retention_days` (mặc định 30 ngày)
    - Xóa logs ERROR cũ hơn `error_retention_days` (mặc định 90 ngày)
    """
    now = datetime.utcnow()
    cutoff_general = now - timedelta(days=retention_days)
    cutoff_error = now - timedelta(days=error_retention_days)

    try:
        # Xóa logs INFO, WARNING cũ
        general_deleted = db.query(SystemLog).filter(
            SystemLog.level != SystemLogLevel.ERROR.value,
            SystemLog.created_at < cutoff_general
        ).delete(synchronize_session=False)

        # Xóa logs ERROR cũ hơn
        error_deleted = db.query(SystemLog).filter(
            SystemLog.level == SystemLogLevel.ERROR.value,
            SystemLog.created_at < cutoff_error
        ).delete(synchronize_session=False)

        db.commit()
        logger.info(
            f"SystemLog cleanup completed: {general_deleted} general logs, "
            f"{error_deleted} error logs deleted."
        )
        return {
            "success": True,
            "general_deleted": general_deleted,
            "error_deleted": error_deleted,
            "total_deleted": general_deleted + error_deleted,
            "retention_days": retention_days,
            "error_retention_days": error_retention_days
        }
    except Exception as exc:
        db.rollback()
        logger.error(f"Error during system log cleanup: {exc}", exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "general_deleted": 0,
            "error_deleted": 0,
            "total_deleted": 0
        }


def run_cleanup_job():
    """Hàm chạy định kỳ hoặc gọi từ cron/CLI."""
    db = get_db_session()
    try:
        return cleanup_expired_system_logs(db=db)
    finally:
        db.close()


if __name__ == "__main__":
    result = run_cleanup_job()
    print("Cleanup result:", result)
