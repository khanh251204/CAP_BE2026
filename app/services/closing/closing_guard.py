"""
Quy tắc chốt sổ dùng chung (xem VoiceCashBook/docs/nghiep_vu_chi_phi_va_chot_so.md, mục 9–10).

1. Không ghi giao dịch MỚI lùi ngày vào kỳ đã chốt (CLOSED). Giao dịch hôm nay luôn ghi được.
   → Sai sót kỳ trước được ghi ở kỳ hiện tại, hoặc người dùng chủ động mở lại kỳ.
2. Mở lại theo thứ bậc: không mở kỳ con (ngày) khi kỳ cha (tháng/quý/năm) chứa nó đang chốt.
3. Không chốt kỳ cha khi còn kỳ con đã mở lại mà chưa chốt lại (số liệu kỳ con chưa được xác nhận).
"""
from datetime import date, datetime
from typing import Optional, Union

from fastapi import HTTPException, status
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.closing_period_model import ClosingPeriod

# Mã lỗi ổn định để client nhận diện (app hỏi người dùng: ghi vào hôm nay / mở lại kỳ)
PERIOD_CLOSED_CODE = "PERIOD_CLOSED"
# Cụm từ có trong mọi thông báo kỳ đã chốt — dùng khi lỗi bị bọc thành chuỗi (MCP)
PERIOD_CLOSED_MARKER = "đã chốt sổ"

_TYPE_RANK = {"DAY": 1, "MONTH": 2, "QUARTER": 3, "YEAR": 4}


def period_label(cp: ClosingPeriod) -> str:
    """Nhãn dễ đọc: 'ngày 15/10/2026', 'tháng 10/2026', 'quý 4/2026', 'năm 2026'."""
    s: date = cp.period_start
    if cp.period_type == "DAY":
        return f"ngày {s.strftime('%d/%m/%Y')}"
    if cp.period_type == "MONTH":
        return f"tháng {s.month}/{s.year}"
    if cp.period_type == "QUARTER":
        return f"quý {(s.month - 1) // 3 + 1}/{s.year}"
    if cp.period_type == "YEAR":
        return f"năm {s.year}"
    return f"{cp.period_start} → {cp.period_end}"


class ClosedPeriodError(HTTPException):
    """409: thao tác chạm vào kỳ đã chốt."""

    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=message)


def _to_date(value: Union[date, datetime, None]) -> date:
    if value is None:
        return datetime.now().date()
    return value.date() if isinstance(value, datetime) else value


def find_closed_period(db: Session, user_id: int, when: Union[date, datetime, None]) -> Optional[ClosingPeriod]:
    """Kỳ CLOSED (bất kỳ cấp nào) chứa ngày `when`, ưu tiên kỳ lớn nhất."""
    d = _to_date(when)
    rows = (
        db.query(ClosingPeriod)
        .filter(
            ClosingPeriod.user_id == user_id,
            ClosingPeriod.status == "CLOSED",
            ClosingPeriod.period_start <= d,
            ClosingPeriod.period_end >= d,
        )
        .all()
    )
    if not rows:
        return None
    return max(rows, key=lambda cp: _TYPE_RANK.get(cp.period_type, 0))


def assert_date_open(db: Session, user_id: int, when: Union[date, datetime, None]) -> None:
    """
    Chặn ghi giao dịch mới LÙI NGÀY vào kỳ đã chốt.

    Giao dịch của hôm nay (hoặc không ghi ngày) luôn được ghi: lịch tự chốt sổ ngày chạy
    trong ngày (vd 22h) nên đơn bán sau giờ chốt vẫn phải ghi được; đồng thời tránh chặn oan
    khi giờ server lệch múi giờ với giờ chốt sổ. So sánh cùng đồng hồ server với transaction_date.
    """
    d = _to_date(when)
    if d >= datetime.now().date():
        return
    with db.no_autoflush:
        closed = find_closed_period(db, user_id, when)
    if closed:
        raise ClosedPeriodError(
            f"Kỳ {period_label(closed)} {PERIOD_CLOSED_MARKER} nên không thể ghi giao dịch ngày "
            f"{d.strftime('%d/%m/%Y')}. Hãy ghi vào kỳ hiện tại (kèm ghi chú kỳ gốc) "
            f"hoặc mở lại kỳ {period_label(closed)}."
        )


def find_transaction_closed_period(
    db: Session,
    user_id: int,
    transaction_id: Optional[int],
    tx_date: Union[date, datetime, None],
) -> Optional[ClosingPeriod]:
    """
    Kỳ CLOSED của user chứa giao dịch: theo snapshot (ClosingTransaction) hoặc theo ngày giao dịch.
    Kỳ OPEN / REOPENED (đã mở lại) không tính. Giao dịch không có ngày chỉ xét theo snapshot.
    """
    from app.models.closing_transaction_model import ClosingTransaction

    with db.no_autoflush:
        if transaction_id is not None:
            linked = (
                db.query(ClosingPeriod)
                .join(ClosingTransaction, ClosingTransaction.closing_id == ClosingPeriod.closing_id)
                .filter(
                    ClosingTransaction.transaction_id == transaction_id,
                    ClosingPeriod.user_id == user_id,
                    ClosingPeriod.status == "CLOSED",
                )
                .all()
            )
            if linked:
                return max(linked, key=lambda cp: _TYPE_RANK.get(cp.period_type, 0))
        if tx_date is None:
            return None
        return find_closed_period(db, user_id, tx_date)


def closed_periods_for_transactions(db: Session, user_id: int, transactions) -> dict:
    """
    Bản gộp của find_transaction_closed_period cho danh sách giao dịch (2 truy vấn cho cả trang).
    Trả về {transaction_id: ClosingPeriod CLOSED}; giao dịch không bị khoá thì không có trong dict.
    """
    from app.models.closing_transaction_model import ClosingTransaction

    txs = [t for t in transactions if t is not None]
    if not txs:
        return {}
    closed = (
        db.query(ClosingPeriod)
        .filter(ClosingPeriod.user_id == user_id, ClosingPeriod.status == "CLOSED")
        .all()
    )
    if not closed:
        return {}
    by_id = {cp.closing_id: cp for cp in closed}
    links: dict = {}
    for tx_id, closing_id in (
        db.query(ClosingTransaction.transaction_id, ClosingTransaction.closing_id)
        .filter(
            ClosingTransaction.transaction_id.in_([t.transaction_id for t in txs]),
            ClosingTransaction.closing_id.in_(list(by_id)),
        )
        .all()
    ):
        links.setdefault(tx_id, []).append(by_id[closing_id])

    result = {}
    for t in txs:
        candidates = list(links.get(t.transaction_id, []))
        if t.transaction_date is not None:
            d = _to_date(t.transaction_date)
            candidates += [cp for cp in closed if cp.period_start <= d <= cp.period_end]
        if candidates:
            result[t.transaction_id] = max(candidates, key=lambda cp: _TYPE_RANK.get(cp.period_type, 0))
    return result


def assert_transaction_editable(db: Session, tx, action: str) -> None:
    """Chặn sửa / xoá giao dịch thuộc kỳ đã chốt (409). `action`: 'sửa' hoặc 'xoá'."""
    closed = find_transaction_closed_period(db, tx.user_id, tx.transaction_id, tx.transaction_date)
    if closed:
        raise ClosedPeriodError(
            f"Giao dịch thuộc kỳ {period_label(closed)} {PERIOD_CLOSED_MARKER} nên không thể {action}. "
            f"Hãy mở lại kỳ {period_label(closed)} nếu cần điều chỉnh."
        )


def assert_can_move_transaction_to(db: Session, user_id: int, new_date: Union[date, datetime]) -> None:
    """Chặn đổi ngày giao dịch sang một ngày thuộc kỳ đã chốt (409), kể cả hôm nay."""
    closed = find_closed_period(db, user_id, new_date)
    if closed:
        raise ClosedPeriodError(
            f"Không thể chuyển giao dịch sang ngày {_to_date(new_date).strftime('%d/%m/%Y')} vì kỳ "
            f"{period_label(closed)} {PERIOD_CLOSED_MARKER}."
        )


def find_closed_parent(db: Session, child: ClosingPeriod) -> Optional[ClosingPeriod]:
    """Kỳ cấp cao hơn đang CLOSED bao trùm kỳ `child`."""
    child_rank = _TYPE_RANK.get(child.period_type, 0)
    rows = (
        db.query(ClosingPeriod)
        .filter(
            ClosingPeriod.user_id == child.user_id,
            ClosingPeriod.closing_id != child.closing_id,
            ClosingPeriod.status == "CLOSED",
            ClosingPeriod.period_start <= child.period_start,
            ClosingPeriod.period_end >= child.period_end,
        )
        .all()
    )
    parents = [cp for cp in rows if _TYPE_RANK.get(cp.period_type, 0) > child_rank]
    if not parents:
        return None
    return max(parents, key=lambda cp: _TYPE_RANK.get(cp.period_type, 0))


def assert_can_reopen(db: Session, closing: ClosingPeriod) -> None:
    """Mở lại theo thứ bậc: kỳ cha đang chốt thì phải mở kỳ cha trước."""
    parent = find_closed_parent(db, closing)
    if parent:
        raise ClosedPeriodError(
            f"Không thể mở lại {period_label(closing)} vì kỳ {period_label(parent)} {PERIOD_CLOSED_MARKER}. "
            f"Hãy mở lại {period_label(parent)} trước."
        )


def assert_no_reopened_children(
    db: Session, user_id: int, period_type: str, period_start: date, period_end: date
) -> None:
    """Không chốt kỳ cha khi còn kỳ con đã mở lại mà chưa chốt lại."""
    rank = _TYPE_RANK.get(period_type, 0)
    rows = (
        db.query(ClosingPeriod)
        .filter(
            ClosingPeriod.user_id == user_id,
            ClosingPeriod.status != "CLOSED",
            ClosingPeriod.period_start >= period_start,
            ClosingPeriod.period_end <= period_end,
        )
        .all()
    )
    children = [cp for cp in rows if _TYPE_RANK.get(cp.period_type, 0) < rank]
    if children:
        names = ", ".join(period_label(cp) for cp in children[:3])
        more = f" và {len(children) - 3} kỳ khác" if len(children) > 3 else ""
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Còn kỳ đã mở lại chưa chốt lại: {names}{more}. Hãy chốt lại các kỳ này trước.",
        )


def period_params_of(cp: ClosingPeriod) -> dict:
    """Dựng lại tham số PeriodService từ kỳ đã lưu (cùng cách create_closing gắn giao dịch)."""
    start: date = cp.period_start
    if cp.period_type == "DAY":
        return {"period_type": "DAY", "date_val": start}
    if cp.period_type == "MONTH":
        return {"period_type": "MONTH", "year": start.year, "month": start.month}
    if cp.period_type == "QUARTER":
        return {"period_type": "QUARTER", "year": start.year, "quarter": (start.month - 1) // 3 + 1}
    return {"period_type": "YEAR", "year": start.year}


def count_late_transactions(db: Session, cp: ClosingPeriod) -> int:
    """
    Số giao dịch thuộc kỳ nhưng KHÔNG có trong snapshot (phát sinh sau giờ chốt).
    > 0 → kỳ "cần chốt lại" để snapshot & báo cáo đầy đủ.
    """
    if cp.status != "CLOSED":
        return 0
    from app.models.transaction_model import Transaction
    from app.models.closing_transaction_model import ClosingTransaction
    from app.services.period_service import PeriodService

    period = PeriodService.resolve_period(**period_params_of(cp))
    linked = db.query(ClosingTransaction.transaction_id).filter(ClosingTransaction.closing_id == cp.closing_id)
    return (
        db.query(Transaction.transaction_id)
        .filter(
            Transaction.user_id == cp.user_id,
            Transaction.transaction_date >= period["start_datetime"],
            Transaction.transaction_date <= period["end_datetime"],
            ~Transaction.transaction_id.in_(linked),
        )
        .count()
    )


def is_period_closed_message(text: Optional[str]) -> bool:
    return bool(text) and PERIOD_CLOSED_MARKER in str(text)


# ---------------------------------------------------------------------------
# Lưới an toàn: mọi giao dịch MỚI (giọng nói, nhập tay, MCP, admin...) đều đi qua flush.
# ---------------------------------------------------------------------------
_installed = False


def _before_flush(session: Session, flush_context, instances) -> None:
    from app.models.transaction_model import Transaction

    for obj in list(session.new):
        if isinstance(obj, Transaction) and obj.user_id is not None:
            assert_date_open(session, obj.user_id, obj.transaction_date)


def install_transaction_guard() -> None:
    """Gắn kiểm tra kỳ đã chốt vào mọi Session (gọi 1 lần khi khởi động)."""
    global _installed
    if _installed:
        return
    event.listen(Session, "before_flush", _before_flush)
    _installed = True
