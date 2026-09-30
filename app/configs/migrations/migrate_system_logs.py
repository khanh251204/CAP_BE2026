import logging
from sqlalchemy import text, inspect
from app.configs.database import engine, Base
from app.models.system_log_model import SystemLog

logger = logging.getLogger(__name__)


def migrate_system_logs():
    """
    Tự động kiểm tra và tạo bảng system_logs kèm các indexes cần thiết
    nếu bảng chưa tồn tại trên database.
    """
    try:
        inspector = inspect(engine)
        tables = [t.lower() for t in inspector.get_table_names()]

        if "system_logs" not in tables:
            logger.info("[Migration] Creating table 'system_logs'...")
            # Tạo bảng system_logs qua Base metadata
            SystemLog.__table__.create(bind=engine, checkfirst=True)
            logger.info("[Migration] Table 'system_logs' created successfully.")
        else:
            # Kiểm tra xem composite index ix_system_logs_created_at_level đã có chưa
            indexes = [idx["name"].lower() for idx in inspector.get_indexes("system_logs")]
            if "ix_system_logs_created_at_level" not in indexes:
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            "CREATE INDEX `ix_system_logs_created_at_level` ON `system_logs` (`created_at`, `level`);"
                        ))
                        logger.info("[Migration] Created index 'ix_system_logs_created_at_level'.")
                except Exception as e:
                    logger.debug(f"[Migration] Composite index note: {e}")

    except Exception as e:
        logger.warning(f"[Migration] migrate_system_logs error: {e}")


def rollback_system_logs():
    """
    Rollback migration: Xóa bảng system_logs.
    """
    try:
        inspector = inspect(engine)
        tables = [t.lower() for t in inspector.get_table_names()]
        if "system_logs" in tables:
            logger.warning("[Migration Rollback] Dropping table 'system_logs'...")
            SystemLog.__table__.drop(bind=engine, checkfirst=True)
            logger.warning("[Migration Rollback] Table 'system_logs' dropped.")
    except Exception as e:
        logger.error(f"[Migration Rollback] rollback_system_logs error: {e}")
