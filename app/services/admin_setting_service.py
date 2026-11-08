"""Admin: xem / đổi cài đặt ghi vết và thống kê dung lượng các bảng log."""
from typing import Any, Dict, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.app_setting_model import AppSetting
from app.models.audit_log_model import AuditLog
from app.models.system_log_model import SystemLog
from app.services import app_setting_service as settings_svc


def _table_sizes(db: Session) -> Dict[str, int]:
    """Dung lượng thật (byte) của các bảng log trên MySQL / TiDB; DB khác (SQLite) thì trả rỗng."""
    try:
        if db.get_bind().dialect.name not in ("mysql", "mariadb"):
            return {}
        rows = db.execute(text(
            "SELECT table_name, COALESCE(data_length, 0) + COALESCE(index_length, 0) "
            "FROM information_schema.tables WHERE table_schema = DATABASE() "
            "AND table_name IN ('Audit_Log', 'system_logs')"
        )).fetchall()
        return {name: int(size) for name, size in rows}
    except Exception:
        return {}


def usage(db: Session) -> Dict[str, Any]:
    audit_by_entity = dict(
        db.query(AuditLog.entity_type, func.count(AuditLog.id)).group_by(AuditLog.entity_type).all()
    )
    audit_oldest = db.query(func.min(AuditLog.created_at)).scalar()
    sys_by_level = dict(db.query(SystemLog.level, func.count(SystemLog.id)).group_by(SystemLog.level).all())
    sys_oldest = db.query(func.min(SystemLog.created_at)).scalar()
    sizes = _table_sizes(db)
    return {
        "audit_log": {
            "total": sum(audit_by_entity.values()),
            "by_entity": {e: int(audit_by_entity.get(e, 0)) for e in settings_svc.AUDIT_ENTITIES},
            "oldest": audit_oldest.isoformat() if audit_oldest else None,
            "size_bytes": sizes.get("Audit_Log"),
        },
        "system_log": {
            "total": sum(sys_by_level.values()),
            "by_level": {k: int(v) for k, v in sys_by_level.items()},
            "oldest": sys_oldest.isoformat() if sys_oldest else None,
            "size_bytes": sizes.get("system_logs"),
        },
    }


def read_settings(db: Session) -> Dict[str, Any]:
    row = db.query(AppSetting).filter(AppSetting.setting_key == settings_svc.OBSERVABILITY_KEY).first()
    return {
        "settings": settings_svc.normalize(row.value if row else None),
        "defaults": settings_svc.defaults(),
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by": row.updated_by if row else None,
        "usage": usage(db),
    }


def update_settings(db: Session, patch: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
    settings_svc.save_settings(db, patch, user_id)
    return read_settings(db)


def reset_settings(db: Session, user_id: Optional[int]) -> Dict[str, Any]:
    settings_svc.reset_settings(db, user_id)
    return read_settings(db)
