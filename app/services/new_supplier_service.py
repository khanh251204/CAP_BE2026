"""
Tạo nhà cung cấp mới ngay trong luồng nhập hàng bằng giọng nói.

Bản nháp không tìm thấy nhà cung cấp -> đánh dấu payload[NEW_SUPPLIER_KEY] = True và hỏi
người dùng có muốn tạo mới không. Khi xác nhận, resolve_supplier_id() chạy trong CÙNG db session
với giao dịch nhập hàng: nhà cung cấp chỉ được flush, giao dịch lỗi thì rollback luôn.
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

NEW_SUPPLIER_KEY = "new_supplier"


def new_supplier_question(supplier_name: str) -> str:
    return f"Nhà cung cấp '{supplier_name}' chưa có trong hệ thống. Bạn có muốn tạo nhà cung cấp mới không? "


def resolve_supplier_id(db: Session, user_id: int, payload: Dict[str, Any]) -> Optional[int]:
    """
    - Có supplier_id -> dùng luôn.
    - Có tên và tìm thấy trong DB (của user) -> id đó.
    - Không tìm thấy nhưng payload được đánh dấu new_supplier -> tạo mới (flush, chưa commit).
    - Còn lại -> None (bên gọi tự báo lỗi).
    """
    from app.services.duplicate_guard import get_or_create_supplier_by_name
    from app.repositories.inventory.inventory_lookup_repo import InventoryLookupRepository

    if payload.get("supplier_id"):
        return payload["supplier_id"]

    name = str(payload.get("supplier_name") or payload.get("supplier") or "").strip()
    if not name:
        return None

    existing = InventoryLookupRepository(db).get_supplier_by_name(user_id, name)
    if existing:
        return existing.supplier_id

    if payload.get(NEW_SUPPLIER_KEY):
        return get_or_create_supplier_by_name(db, user_id, name).supplier_id
    return None
