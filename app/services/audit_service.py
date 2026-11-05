"""
Audit Log: tự ghi vết mỗi lần giao dịch (Transaction, Transaction_Detail), công nợ (Debt, Debt_Payment)
và biến động kho (Inventory_Transaction) được tạo, sửa, xoá.

Dùng sự kiện ORM (mapper events) thay vì gọi tay ở từng nơi, nên mọi đường vào đều có vết:
giọng nói, nhập tay, ghi nợ, sửa / xoá giao dịch, tác vụ của admin, tác vụ nền.
Vết được ghi bằng chính connection của thao tác gốc (cùng database transaction):
thao tác rollback thì vết cũng rollback, không có vết "ma".

Người thực hiện lấy từ ContextVar do SystemLogMiddleware đặt theo token của request.
"""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Iterator, Optional

from sqlalchemy import event, inspect, select

from app.models.audit_log_model import AuditLog
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.transaction_model import Transaction

logger = logging.getLogger(__name__)

ENTITY_TRANSACTION = "TRANSACTION"
ENTITY_DETAIL = "TRANSACTION_DETAIL"
ENTITY_DEBT = "DEBT"
ENTITY_DEBT_PAYMENT = "DEBT_PAYMENT"
ENTITY_INVENTORY = "INVENTORY"

ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"
ROLE_SYSTEM = "SYSTEM"

# Trường chỉ đổi theo thời gian, không phải thay đổi nghiệp vụ
_IGNORED_FIELDS = {"updated_at"}

# {"user_id": int | None, "role": "USER" | "ADMIN" | "SYSTEM", "api_path": str, "http_method": str}
current_actor_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar("audit_current_actor", default=None)


@contextmanager
def audit_actor(user_id: Optional[int], role: str = ROLE_USER, **extra: Any) -> Iterator[None]:
    """Gán người thực hiện cho các thao tác trong khối (script, tác vụ nền, test)."""
    token = current_actor_var.set({"user_id": user_id, "role": role, **extra})
    try:
        yield
    finally:
        current_actor_var.reset(token)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _attr_keys(target: Any) -> list:
    mapper = inspect(target).mapper
    return [mapper.get_property_by_column(c).key for c in mapper.local_table.columns]


def _snapshot(target: Any) -> Dict[str, Any]:
    return {k: _json_safe(getattr(target, k, None)) for k in _attr_keys(target)}


def _changes(target: Any) -> Dict[str, Dict[str, Any]]:
    """Trường nào đổi từ giá trị nào sang giá trị nào (bỏ qua trường chỉ đổi theo thời gian)."""
    state = inspect(target)
    out: Dict[str, Dict[str, Any]] = {}
    for key in _attr_keys(target):
        if key in _IGNORED_FIELDS:
            continue
        hist = state.attrs[key].history
        if not hist.has_changes():
            continue
        before = hist.deleted[0] if hist.deleted else None
        after = hist.added[0] if hist.added else getattr(target, key, None)
        if _json_safe(before) == _json_safe(after):
            continue
        out[key] = {"before": _json_safe(before), "after": _json_safe(after)}
    return out


def _owner_of_transaction(connection: Any, transaction_id: Optional[int]) -> Optional[int]:
    if transaction_id is None:
        return None
    try:
        row = connection.execute(
            select(Transaction.__table__.c.user_id).where(Transaction.__table__.c.transaction_id == transaction_id)
        ).first()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def _write(connection: Any, *, entity_type: str, entity_id: Optional[int], transaction_id: Optional[int],
           action: str, owner_user_id: Optional[int], source: Optional[str],
           before: Optional[dict], after: Optional[dict], changes: Optional[dict]) -> None:
    try:
        from app.middlewares.system_log_middleware import get_current_request_id
        from app.services.app_setting_service import get_audit_settings

        cfg = get_audit_settings()
        if not cfg["enabled"].get(entity_type, False):
            return  # admin đã tắt ghi vết cho chức năng này
        if action == "UPDATE" and not cfg["full_snapshots"]:
            before = after = None  # chỉ giữ các trường đổi để nhẹ DB

        actor = current_actor_var.get() or {}
        req_id = get_current_request_id()
        connection.execute(
            AuditLog.__table__.insert().values(
                created_at=datetime.now(),
                entity_type=entity_type,
                entity_id=entity_id,
                transaction_id=transaction_id,
                action=action,
                owner_user_id=owner_user_id,
                actor_user_id=actor.get("user_id"),
                actor_role=actor.get("role") or ROLE_SYSTEM,
                source=source,
                request_id=str(req_id)[:64] if req_id else None,
                api_path=(str(actor.get("api_path"))[:255] if actor.get("api_path") else None),
                http_method=actor.get("http_method"),
                before_data=before,
                after_data=after,
                changes=changes,
            )
        )
    except Exception as exc:  # vết hỏng không được làm hỏng giao dịch thật
        logger.warning("[Audit] không ghi được vết %s %s: %s", entity_type, action, exc)


# ---------------------------------------------------------------- Cấu hình từng loại đối tượng

def _owner_from_debt(connection: Any, target: Any) -> Optional[int]:
    try:
        row = connection.execute(
            select(Debt.__table__.c.user_id).where(Debt.__table__.c.debt_id == target.debt_id)
        ).first()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


# model, loại đối tượng, thuộc tính id, thuộc tính giao dịch cha, cách tìm chủ dữ liệu, cách lấy nguồn nhập
_SPECS = [
    (Transaction, ENTITY_TRANSACTION, "transaction_id", "transaction_id",
     lambda c, t: t.user_id, lambda t: _json_safe(getattr(t, "input_method", None))),
    (TransactionDetail, ENTITY_DETAIL, "detail_id", "transaction_id",
     lambda c, t: _owner_of_transaction(c, t.transaction_id), lambda t: None),
    (Debt, ENTITY_DEBT, "debt_id", "transaction_id",
     lambda c, t: t.user_id, lambda t: None),
    (DebtPayment, ENTITY_DEBT_PAYMENT, "payment_id", "transaction_id",
     _owner_from_debt, lambda t: None),
    (InventoryTransaction, ENTITY_INVENTORY, "inventory_transaction_id", "transaction_id",
     lambda c, t: t.user_id, lambda t: None),
]


def _make_handlers(entity_type: str, id_attr: str, tx_attr: str, owner_of: Callable, source_of: Callable):
    def common(connection: Any, target: Any) -> Dict[str, Any]:
        return {
            "entity_type": entity_type,
            "entity_id": getattr(target, id_attr, None),
            "transaction_id": getattr(target, tx_attr, None),
            "owner_user_id": owner_of(connection, target),
            "source": source_of(target),
        }

    def after_insert(mapper, connection, target):
        _write(connection, action="CREATE", before=None, after=_snapshot(target), changes=None,
               **common(connection, target))

    def after_update(mapper, connection, target):
        changes = _changes(target)
        if not changes:
            return
        after = _snapshot(target)
        before = {**after, **{k: v["before"] for k, v in changes.items()}}
        _write(connection, action="UPDATE", before=before, after=after, changes=changes,
               **common(connection, target))

    def after_delete(mapper, connection, target):
        _write(connection, action="DELETE", before=_snapshot(target), after=None, changes=None,
               **common(connection, target))

    return after_insert, after_update, after_delete


_registered = False


def register_audit_listeners() -> None:
    """Gắn sự kiện ORM một lần. Gọi từ app/models/__init__.py nên mọi tiến trình đều có."""
    global _registered
    if _registered:
        return
    for model, entity_type, id_attr, tx_attr, owner_of, source_of in _SPECS:
        ins, upd, dele = _make_handlers(entity_type, id_attr, tx_attr, owner_of, source_of)
        event.listen(model, "after_insert", ins)
        event.listen(model, "after_update", upd)
        event.listen(model, "after_delete", dele)
    _registered = True
