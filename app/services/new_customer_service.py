"""
Tạo khách hàng mới ngay trong luồng giao dịch bằng giọng nói.

Bản nháp (handler) không tìm thấy khách hàng -> đánh dấu payload[NEW_CUSTOMER_KEY] = True
và hỏi người dùng có muốn tạo mới không. Khi người dùng xác nhận, bước thực thi gọi
resolve_customer_id() trong CÙNG db session với giao dịch: khách hàng chỉ được flush,
nếu giao dịch lỗi thì rollback luôn cả khách hàng vừa tạo.
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

NEW_CUSTOMER_KEY = "new_customer"


def new_customer_question(customer_name: str) -> str:
    return f"Khách hàng '{customer_name}' chưa có trong hệ thống. Bạn có muốn tạo khách hàng mới không? "


def resolve_customer_id(db: Session, user_id: int, payload: Dict[str, Any]) -> Optional[int]:
    """
    Trả về customer_id cho payload:
    - Có customer_id -> dùng luôn.
    - Có tên khách và tìm thấy trong DB (của user) -> id đó.
    - Không tìm thấy nhưng payload được đánh dấu new_customer -> tạo mới (flush, chưa commit).
    - Còn lại -> None (bên gọi tự báo lỗi).
    """
    from app.services.duplicate_guard import get_or_create_customer_by_name
    from app.repositories.inventory.inventory_lookup_repo import InventoryLookupRepository

    if payload.get("customer_id"):
        return payload["customer_id"]

    name = str(payload.get("customer_name") or payload.get("customer") or "").strip()
    if not name:
        return None

    existing = InventoryLookupRepository(db).get_customer_by_name(user_id, name)
    if existing:
        return existing.customer_id

    if payload.get(NEW_CUSTOMER_KEY):
        return get_or_create_customer_by_name(db, user_id, name).customer_id
    return None
