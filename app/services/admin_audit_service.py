"""Admin: tra cứu Audit Log giao dịch."""
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.audit_log_model import AuditLog
from app.models.user_model import User


def _names(db: Session, ids: set) -> Dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    rows = db.query(User.user_id, User.full_name, User.email).filter(User.user_id.in_(ids)).all()
    return {uid: (name or email or f"#{uid}") for uid, name, email in rows}


def _to_item(row: AuditLog, names: Dict[int, str]) -> Dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "transaction_id": row.transaction_id,
        "action": row.action,
        "owner_user_id": row.owner_user_id,
        "owner_name": names.get(row.owner_user_id),
        "actor_user_id": row.actor_user_id,
        "actor_name": names.get(row.actor_user_id),
        "actor_role": row.actor_role,
        "source": row.source,
        "request_id": row.request_id,
        "api_path": row.api_path,
        "http_method": row.http_method,
        "before_data": row.before_data,
        "after_data": row.after_data,
        "changes": row.changes,
    }


def _filtered(
    db: Session,
    entity_type: Optional[str],
    action: Optional[str],
    actor_role: Optional[str],
    transaction_id: Optional[int],
    user_id: Optional[int],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
):
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type.upper().strip())
    if action:
        q = q.filter(AuditLog.action == action.upper().strip())
    if actor_role:
        q = q.filter(AuditLog.actor_role == actor_role.upper().strip())
    if transaction_id is not None:
        q = q.filter(AuditLog.transaction_id == transaction_id)
    if user_id is not None:
        # Theo người thực hiện hoặc chủ dữ liệu
        q = q.filter(or_(AuditLog.actor_user_id == user_id, AuditLog.owner_user_id == user_id))
    if date_from:
        q = q.filter(AuditLog.created_at >= date_from)
    if date_to:
        q = q.filter(AuditLog.created_at <= date_to)
    return q


class AdminAuditService:
    @staticmethod
    def list_logs(
        db: Session,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        actor_role: Optional[str] = None,
        transaction_id: Optional[int] = None,
        user_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        q = _filtered(db, entity_type, action, actor_role, transaction_id, user_id, date_from, date_to)
        total = q.count()
        rows = (
            q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        names = _names(db, {r.owner_user_id for r in rows} | {r.actor_user_id for r in rows})
        return [_to_item(r, names) for r in rows], total, (math.ceil(total / page_size) if total else 0)

    @staticmethod
    def transaction_timeline(db: Session, transaction_id: int) -> List[Dict[str, Any]]:
        """Toàn bộ vòng đời một giao dịch (kể cả đã xoá), cũ trước mới sau."""
        rows = (
            db.query(AuditLog)
            .filter(AuditLog.transaction_id == transaction_id)
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
            .all()
        )
        names = _names(db, {r.owner_user_id for r in rows} | {r.actor_user_id for r in rows})
        return [_to_item(r, names) for r in rows]

    @staticmethod
    def summary(
        db: Session,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, int]:
        q = _filtered(db, None, None, None, None, None, date_from, date_to)
        by_action = dict(
            q.with_entities(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()
        )
        admin_actions = q.filter(AuditLog.actor_role == "ADMIN").count()
        distinct_tx = (
            q.filter(AuditLog.transaction_id.isnot(None))
            .with_entities(func.count(func.distinct(AuditLog.transaction_id)))
            .scalar()
        ) or 0
        return {
            "total": sum(by_action.values()),
            "create_count": by_action.get("CREATE", 0),
            "update_count": by_action.get("UPDATE", 0),
            "delete_count": by_action.get("DELETE", 0),
            "admin_actions": admin_actions,
            "distinct_transactions": distinct_tx,
        }
