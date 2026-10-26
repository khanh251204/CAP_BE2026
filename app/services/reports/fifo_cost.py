"""
Giá vốn hàng bán theo FIFO (nhập trước – xuất trước).

Đi lần lượt sổ kho (Inventory_Transaction) của từng sản phẩm:
- IN của giao dịch mua/nhập hàng  -> tạo lô với giá nhập của giao dịch đó.
- IN khác (nhập kho nội bộ, tồn đầu), ADJUSTMENT tăng -> tạo lô, giá = giá nhập gần nhất.
- OUT của giao dịch bán hàng      -> lấy hàng từ lô cũ nhất, ghi giá vốn cho giao dịch bán.
- OUT khác (xuất kho nội bộ), DAMAGE, ADJUSTMENT giảm -> lấy hàng từ lô cũ nhất, không tính giá vốn bán.
Hết lô mà vẫn xuất -> phần thiếu tính theo giá nhập gần nhất.

Ví dụ: nhập 10 lon x 8.000đ, nhập 10 lon x 10.000đ, bán 10 lon -> giá vốn 80.000đ;
bán tiếp 10 lon -> 100.000đ (cộng dồn 180.000đ).
"""
from bisect import bisect_right
from collections import defaultdict, deque
from decimal import Decimal
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.intent_model import Intent
from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.transaction_model import Transaction

PURCHASE_INTENTS = ("mua_hang", "nhap_hang")
SALE_INTENTS = ("ban_hang",)
ZERO = Decimal("0")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else ZERO


class _PriceHistory:
    """Giá nhập theo thời gian của một sản phẩm — dùng cho lô không có giá nhập."""

    def __init__(self, points: List[Tuple]):
        self.points = sorted(points, key=lambda p: p[0])
        self.times = [p[0] for p in self.points]

    def at(self, when) -> Decimal:
        if not self.points:
            return ZERO
        if when is None:
            return self.points[-1][1]
        idx = bisect_right(self.times, when) - 1
        # Chưa từng nhập trước thời điểm này -> lấy giá nhập sớm nhất
        return self.points[idx][1] if idx >= 0 else self.points[0][1]


def fifo_sale_costs(
    db: Session, user_id: int, product_ids: Iterable[int]
) -> Dict[Tuple[int, int], Tuple[Decimal, Decimal]]:
    """
    Trả về {(transaction_id bán, product_id): (số lượng đã xuất kho, giá vốn FIFO)}.
    Chỉ tính trên dữ liệu của user (multi-tenant).
    """
    product_ids = [p for p in set(product_ids) if p]
    if not product_ids:
        return {}

    # Giá nhập của từng giao dịch mua: (transaction_id, product_id) -> đơn giá bình quân trong giao dịch
    purchase_rows = (
        db.query(
            TransactionDetail.transaction_id,
            TransactionDetail.product_id,
            Transaction.transaction_date,
            func.sum(TransactionDetail.subtotal),
            func.sum(TransactionDetail.quantity),
        )
        .join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)
        .join(Intent, Transaction.intent_id == Intent.intent_id)
        .filter(
            Transaction.user_id == user_id,
            Intent.intent_name.in_(PURCHASE_INTENTS),
            TransactionDetail.product_id.in_(product_ids),
        )
        .group_by(TransactionDetail.transaction_id, TransactionDetail.product_id, Transaction.transaction_date)
        .all()
    )
    purchase_price: Dict[Tuple[int, int], Decimal] = {}
    history_points: Dict[int, List[Tuple]] = defaultdict(list)
    for tx_id, pid, tx_date, subtotal, qty in purchase_rows:
        qty_d = _dec(qty)
        if qty_d <= 0:
            continue
        price = _dec(subtotal) / qty_d
        purchase_price[(tx_id, pid)] = price
        history_points[pid].append((tx_date, price))
    histories = {pid: _PriceHistory(pts) for pid, pts in history_points.items()}

    # Giao dịch bán của user (để biết OUT nào là bán hàng)
    sale_tx_ids = {
        tx_id
        for (tx_id,) in db.query(Transaction.transaction_id)
        .join(Intent, Transaction.intent_id == Intent.intent_id)
        .filter(Transaction.user_id == user_id, Intent.intent_name.in_(SALE_INTENTS))
        .all()
    }

    ledger = (
        db.query(InventoryTransaction)
        .filter(
            InventoryTransaction.user_id == user_id,
            InventoryTransaction.product_id.in_(product_ids),
        )
        .order_by(
            InventoryTransaction.product_id,
            InventoryTransaction.created_at,
            InventoryTransaction.inventory_transaction_id,
        )
        .all()
    )

    result: Dict[Tuple[int, int], Tuple[Decimal, Decimal]] = {}
    lots: Dict[int, deque] = defaultdict(deque)  # product_id -> deque([qty, unit_cost])

    def take(pid: int, qty: Decimal, when) -> Decimal:
        """Lấy qty từ lô cũ nhất, trả về tổng giá vốn."""
        cost = ZERO
        queue = lots[pid]
        while qty > 0 and queue:
            lot = queue[0]
            used = min(qty, lot[0])
            cost += used * lot[1]
            lot[0] -= used
            qty -= used
            if lot[0] <= 0:
                queue.popleft()
        if qty > 0:
            # Xuất quá số lô ghi nhận được (thiếu dữ liệu nhập) -> giá nhập gần nhất
            history = histories.get(pid)
            cost += qty * (history.at(when) if history else ZERO)
        return cost

    def add(pid: int, qty: Decimal, unit_cost: Decimal) -> None:
        if qty > 0:
            lots[pid].append([qty, unit_cost])

    for row in ledger:
        pid = row.product_id
        qty = _dec(row.quantity)
        history = histories.get(pid)
        fallback = history.at(row.created_at) if history else ZERO

        if row.inventory_type == "IN":
            add(pid, qty, purchase_price.get((row.transaction_id, pid), fallback))
        elif row.inventory_type == "ADJUSTMENT":
            delta = _dec(row.quantity_after) - _dec(row.quantity_before)
            if delta > 0:
                add(pid, delta, fallback)
            elif delta < 0:
                take(pid, -delta, row.created_at)
        elif row.inventory_type == "OUT" and row.transaction_id in sale_tx_ids:
            cost = take(pid, qty, row.created_at)
            key = (row.transaction_id, pid)
            prev_qty, prev_cost = result.get(key, (ZERO, ZERO))
            result[key] = (prev_qty + qty, prev_cost + cost)
        else:  # OUT nội bộ, DAMAGE
            take(pid, qty, row.created_at)

    return result


def latest_purchase_price(db: Session, user_id: int, product_id: int, end_dt) -> Decimal:
    """Giá nhập gần nhất tới end_dt (không có thì giá nhập gần nhất bất kỳ) — cho phần bán không qua sổ kho."""
    base = (
        db.query(TransactionDetail.unit_price)
        .join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)
        .join(Intent, Transaction.intent_id == Intent.intent_id)
        .filter(
            Transaction.user_id == user_id,
            Intent.intent_name.in_(PURCHASE_INTENTS),
            TransactionDetail.product_id == product_id,
        )
        .order_by(Transaction.transaction_date.desc(), TransactionDetail.detail_id.desc())
    )
    row = base.filter(Transaction.transaction_date <= end_dt).first() or base.first()
    return _dec(row[0]) if row and row[0] is not None else ZERO
