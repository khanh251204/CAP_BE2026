"""
Dọn dữ liệu ghi vết theo thời gian giữ do admin cài (App_Setting "observability"):
- Audit_Log: xoá vết cũ hơn audit.retention_days (0 = giữ mãi).
- system_logs: INFO / WARNING cũ hơn system_log.retention_days, ERROR cũ hơn error_retention_days.

Trước đây system_logs chỉ có hàm dọn mà không được lịch nào gọi, nên bảng phình mãi.
Xoá theo lô nhỏ để không khoá bảng lâu trên MySQL / TiDB.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.models.audit_log_model import AuditLog
from app.models.system_log_model import SystemLog, SystemLogLevel
from app.services.app_setting_service import get_settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 2000
MAX_BATCHES = 200  # tối đa 400.000 dòng mỗi lần chạy, phần còn lại để lần sau


def _delete_in_batches(db: Session, model: Any, id_col: Any, *conditions: Any) -> int:
    total = 0
    for _ in range(MAX_BATCHES):
        ids = [r[0] for r in db.query(id_col).filter(*conditions).limit(BATCH_SIZE).all()]
        if not ids:
            break
        db.query(model).filter(id_col.in_(ids)).delete(synchronize_session=False)
        db.commit()
        total += len(ids)
        if len(ids) < BATCH_SIZE:
            break
    return total


def cleanup_audit_logs(db: Session, retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = datetime.now() - timedelta(days=retention_days)
    return _delete_in_batches(db, AuditLog, AuditLog.id, AuditLog.created_at < cutoff)


def cleanup_system_logs(db: Session, retention_days: int, error_retention_days: int) -> Dict[str, int]:
    now = datetime.now()
    general = _delete_in_batches(
        db, SystemLog, SystemLog.id,
        SystemLog.level != SystemLogLevel.ERROR.value,
        SystemLog.created_at < now - timedelta(days=retention_days),
    )
    errors = _delete_in_batches(
        db, SystemLog, SystemLog.id,
        SystemLog.level == SystemLogLevel.ERROR.value,
        SystemLog.created_at < now - timedelta(days=error_retention_days),
    )
    return {"general": general, "error": errors}


def run_retention(db: Session) -> Dict[str, Any]:
    """Dọn theo cài đặt hiện hành, trả số dòng đã xoá."""
    cfg = get_settings()
    audit_deleted = cleanup_audit_logs(db, cfg["audit"]["retention_days"])
    sys_deleted = cleanup_system_logs(
        db, cfg["system_log"]["retention_days"], cfg["system_log"]["error_retention_days"]
    )
    result = {
        "audit_deleted": audit_deleted,
        "system_log_deleted": sys_deleted["general"] + sys_deleted["error"],
    }
    if any(result.values()):
        logger.info("[Retention] đã dọn: %s", result)
    return result


class DataRetentionScheduler:
    """Chạy dọn dữ liệu ghi vết mỗi ngày (mặc định 24 giờ), lần đầu sau khi server khởi động 60 giây."""

    _is_running = False
    _task = None
    _interval_seconds = int(os.getenv("DATA_RETENTION_INTERVAL_SECONDS", "86400"))

    @classmethod
    def start(cls) -> None:
        if cls._is_running:
            return
        cls._is_running = True
        cls._task = asyncio.create_task(cls._loop())
        logger.info("[Retention] Scheduler chạy mỗi %ss.", cls._interval_seconds)

    @classmethod
    def stop(cls) -> None:
        cls._is_running = False
        if cls._task:
            cls._task.cancel()

    @classmethod
    def run_once(cls) -> Dict[str, Any]:
        db = get_db_session()
        try:
            return run_retention(db)
        except Exception as exc:
            db.rollback()
            logger.error("[Retention] lỗi dọn dữ liệu: %s", exc, exc_info=True)
            return {"audit_deleted": 0, "system_log_deleted": 0, "error": str(exc)}
        finally:
            db.close()

    @classmethod
    async def _loop(cls) -> None:
        await asyncio.sleep(60)
        while cls._is_running:
            await asyncio.to_thread(cls.run_once)
            await asyncio.sleep(cls._interval_seconds)
