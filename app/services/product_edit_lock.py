"""
Khóa sửa TÊN và ĐƠN VỊ của sản phẩm (đơn giá, định mức, ảnh... vẫn sửa bình thường).

Quy tắc:
- Sản phẩm CHƯA phát sinh giao dịch nào (mua bán, nhập/xuất kho, kiểm kê) và còn trong 24h
  kể từ lúc tạo -> được sửa tên và đơn vị.
- Đã phát sinh giao dịch (dù kỳ đã chốt sổ hay chưa) -> khóa.
- Quá 24h kể từ lúc tạo -> khóa.

Lý do: tên / đơn vị đi vào sổ sách và tồn kho, đổi về sau làm lệch lịch sử giao dịch.
"""
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail

EDIT_WINDOW = timedelta(hours=24)

REASON_HAS_TRANSACTIONS = "HAS_TRANSACTIONS"
REASON_WINDOW_EXPIRED = "WINDOW_EXPIRED"

MESSAGES = {
    REASON_HAS_TRANSACTIONS: "Sản phẩm đã phát sinh giao dịch nên không thể sửa tên và đơn vị.",
    REASON_WINDOW_EXPIRED: "Đã quá 24 giờ kể từ khi tạo sản phẩm nên không thể sửa tên và đơn vị.",
}


def product_ids_with_transactions(db: Session, product_ids: Iterable[int]) -> set:
    """Các product_id đã có dòng giao dịch hoặc biến động kho."""
    ids = list(product_ids)
    if not ids:
        return set()
    used = {
        pid for (pid,) in db.query(TransactionDetail.product_id)
        .filter(TransactionDetail.product_id.in_(ids)).distinct().all()
    }
    used |= {
        pid for (pid,) in db.query(InventoryTransaction.product_id)
        .filter(InventoryTransaction.product_id.in_(ids)).distinct().all()
    }
    return used


def build_lock(created_at: Optional[datetime], has_transactions: bool, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now()
    editable_until = (created_at + EDIT_WINDOW) if created_at else None
    if has_transactions:
        reason = REASON_HAS_TRANSACTIONS
    elif editable_until is not None and now > editable_until:
        reason = REASON_WINDOW_EXPIRED
    else:
        reason = None
    return {
        "name_locked": reason is not None,
        "name_lock_reason": reason,
        "name_lock_message": MESSAGES.get(reason) if reason else None,
        # Chỉ có ý nghĩa khi chưa khóa: hạn chót để sửa tên / đơn vị
        "name_editable_until": editable_until.isoformat() if (editable_until and reason is None) else None,
    }


def get_lock(db: Session, product) -> dict:
    used = product_ids_with_transactions(db, [product.product_id])
    return build_lock(product.created_at, product.product_id in used)


def get_locks(db: Session, products: Iterable) -> dict:
    """{product_id: lock dict} cho nhiều sản phẩm (2 truy vấn)."""
    products = list(products)
    used = product_ids_with_transactions(db, [p.product_id for p in products])
    now = datetime.now()
    return {p.product_id: build_lock(p.created_at, p.product_id in used, now) for p in products}
