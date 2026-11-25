"""
Admin Debt Management — Service Layer

Cung cấp truy vấn công nợ toàn hệ thống (cross-user) cho Admin:
- Danh sách công nợ có phân trang, tìm kiếm (mã nợ, khách hàng, nhà cung cấp, chủ cửa hàng, nội dung giao dịch),
  lọc theo chiều nợ (RECEIVABLE / PAYABLE), trạng thái (UNPAID / PARTIAL / PAID), user_id, khoảng ngày.
- Thống kê tổng quan KPI công nợ trên toàn bộ kết quả lọc.
- Chi tiết khoản công nợ kèm thông tin cửa hàng, đối tác, giao dịch gốc và lịch sử các lần thanh toán.
"""
from math import ceil
from typing import Optional, Dict, List, Any

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_, and_, case, cast, String
from sqlalchemy.orm import Session, joinedload

from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.user_model import User
from app.models.store_model import Store
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.services.transaction_service import resolve_intent_type


class AdminDebtService:

    @staticmethod
    def list_debts(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        direction: Optional[str] = None,
        status_filter: Optional[str] = None,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        stmt = (
            select(Debt)
            .options(
                joinedload(Debt.user),
                joinedload(Debt.customer),
                joinedload(Debt.supplier),
                joinedload(Debt.transaction).joinedload(Transaction.intent),
                joinedload(Debt.payments),
            )
        )
        count_stmt = select(func.count(Debt.debt_id)).select_from(Debt)

        filters = dict(
            search=search,
            user_id=user_id,
            direction=direction,
            status_filter=status_filter,
            customer_id=customer_id,
            supplier_id=supplier_id,
            date_from=date_from,
            date_to=date_to,
        )
        stmt = _apply_debt_filters(stmt, **filters)
        count_stmt = _apply_debt_filters(count_stmt, **filters)

        total = int(db.scalar(count_stmt) or 0)

        sort_col = _resolve_sort_column(sort_by)
        order_fn = desc if sort_order.lower() == "desc" else lambda c: c.asc()
        stmt = stmt.order_by(order_fn(sort_col), desc(Debt.debt_id))

        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        debts = db.scalars(stmt).unique().all()
        total_pages = ceil(total / limit) if limit > 0 else 0

        items = [_serialize_debt_list_item(d) for d in debts]
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        }

    @staticmethod
    def get_summary(
        db: Session,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        direction: Optional[str] = None,
        status_filter: Optional[str] = None,
        customer_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Thống kê KPI công nợ theo bộ lọc.
        Lưu ý: Bỏ qua bộ lọc `direction` và `status_filter` khi tính các thẻ nhóm đối xứng
        hoặc tính đầy đủ trên tập dữ liệu lọc theo search/user/date để các thẻ KPI luôn hiển thị
        đủ số liệu Tổng phải thu / Tổng phải trả / Trạng thái thanh toán.
        """
        base_filters = dict(
            search=search,
            user_id=user_id,
            direction=direction,
            status_filter=status_filter,
            customer_id=customer_id,
            supplier_id=supplier_id,
            date_from=date_from,
            date_to=date_to,
        )

        def sum_col(cond, col):
            return func.coalesce(func.sum(case((cond, col), else_=0)), 0)

        def count_cond(cond):
            return func.coalesce(func.sum(case((cond, 1), else_=0)), 0)

        is_rec = Debt.direction == "RECEIVABLE"
        is_pay = Debt.direction == "PAYABLE"

        stmt = select(
            func.count(Debt.debt_id),
            count_cond(Debt.status == "UNPAID"),
            count_cond(Debt.status == "PARTIAL"),
            count_cond(Debt.status == "PAID"),
            count_cond(is_rec),
            count_cond(is_pay),
            sum_col(is_rec, Debt.original_amount),
            sum_col(is_rec, Debt.remaining_debt),
            sum_col(is_pay, Debt.original_amount),
            sum_col(is_pay, Debt.remaining_debt),
        ).select_from(Debt)

        row = db.execute(_apply_debt_filters(stmt, **base_filters)).one()
        (
            total_count,
            unpaid_count,
            partial_count,
            paid_count,
            rec_count,
            pay_count,
            rec_orig,
            rec_rem,
            pay_orig,
            pay_rem,
        ) = row

        rec_orig_f = float(rec_orig or 0.0)
        rec_rem_f = float(rec_rem or 0.0)
        rec_paid_f = max(0.0, rec_orig_f - rec_rem_f)

        pay_orig_f = float(pay_orig or 0.0)
        pay_rem_f = float(pay_rem or 0.0)
        pay_paid_f = max(0.0, pay_orig_f - pay_rem_f)

        return {
            "total_count": int(total_count or 0),
            "unpaid_count": int(unpaid_count or 0),
            "partial_count": int(partial_count or 0),
            "paid_count": int(paid_count or 0),
            "receivable_count": int(rec_count or 0),
            "payable_count": int(pay_count or 0),
            "receivable_original": rec_orig_f,
            "receivable_paid": rec_paid_f,
            "receivable_remaining": rec_rem_f,
            "payable_original": pay_orig_f,
            "payable_paid": pay_paid_f,
            "payable_remaining": pay_rem_f,
            "net_remaining": rec_rem_f - pay_rem_f,
        }

    @staticmethod
    def get_debt_detail(db: Session, debt_id: int) -> Dict[str, Any]:
        stmt = (
            select(Debt)
            .options(
                joinedload(Debt.user),
                joinedload(Debt.customer),
                joinedload(Debt.supplier),
                joinedload(Debt.payments).joinedload(DebtPayment.account),
                joinedload(Debt.transaction).joinedload(Transaction.intent),
                joinedload(Debt.transaction)
                .joinedload(Transaction.transaction_detail)
                .joinedload(TransactionDetail.product),
            )
            .filter(Debt.debt_id == debt_id)
        )
        debt = db.scalars(stmt).unique().first()
        if not debt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy khoản công nợ với ID {debt_id}",
            )
        return _serialize_debt_detail(debt)

    @staticmethod
    def get_debt_payments(db: Session, debt_id: int) -> List[Dict[str, Any]]:
        debt = db.scalars(select(Debt).filter(Debt.debt_id == debt_id)).first()
        if not debt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy khoản công nợ với ID {debt_id}",
            )
        stmt = (
            select(DebtPayment)
            .options(joinedload(DebtPayment.account))
            .filter(DebtPayment.debt_id == debt_id)
            .order_by(desc(DebtPayment.payment_date), desc(DebtPayment.payment_id))
        )
        payments = db.scalars(stmt).unique().all()
        return [_serialize_payment(p) for p in payments]


# ========================================
# Private helpers
# ========================================

def _ilike(column, term: str):
    return column.ilike(f"%{term}%")


def _apply_debt_filters(
    stmt,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    direction: Optional[str] = None,
    status_filter: Optional[str] = None,
    customer_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    stmt = (
        stmt.outerjoin(Customer, Debt.customer_id == Customer.customer_id)
        .outerjoin(Supplier, Debt.supplier_id == Supplier.supplier_id)
        .outerjoin(Transaction, Debt.transaction_id == Transaction.transaction_id)
    )

    if user_id is not None:
        stmt = stmt.filter(Debt.user_id == user_id)
    if direction and direction.strip():
        d_val = direction.strip().upper()
        if d_val in ("RECEIVABLE", "PAYABLE"):
            stmt = stmt.filter(Debt.direction == d_val)
    if status_filter and status_filter.strip():
        s_val = status_filter.strip().upper()
        if s_val == "OPEN":
            stmt = stmt.filter(Debt.status.in_(["UNPAID", "PARTIAL"]))
        elif s_val in ("UNPAID", "PARTIAL", "PAID"):
            stmt = stmt.filter(Debt.status == s_val)
    if customer_id is not None:
        stmt = stmt.filter(Debt.customer_id == customer_id)
    if supplier_id is not None:
        stmt = stmt.filter(Debt.supplier_id == supplier_id)
    if date_from:
        stmt = stmt.filter(Debt.created_at >= date_from)
    if date_to:
        stmt = stmt.filter(Debt.created_at <= date_to)

    if search and search.strip():
        term = search.strip()
        id_term = (
            term.upper()
            .replace("DEBT-", "")
            .replace("CN-", "")
            .replace("NO-", "")
            .replace("#", "")
            .strip()
        )
        stmt = stmt.outerjoin(User, Debt.user_id == User.user_id)
        conditions = [
            cast(Debt.debt_id, String).ilike(f"%{term}%"),
            _ilike(Customer.customer_name, term),
            _ilike(Customer.phone_number, term),
            _ilike(Supplier.supplier_name, term),
            _ilike(Supplier.phone_number, term),
            _ilike(User.full_name, term),
            _ilike(User.email, term),
            _ilike(User.phone_number, term),
            User.store_rel.has(_ilike(Store.store_name, term)),
            _ilike(Transaction.input_text, term),
            _ilike(Transaction.note, term),
        ]
        if id_term and id_term != term:
            conditions.append(cast(Debt.debt_id, String).ilike(f"%{id_term}%"))
        stmt = stmt.filter(or_(*conditions))

    return stmt


def _safe_dt(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _safe_user(user) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "business_type": user.business_type,
        "store_name": user.store_name,
        "role": user.role,
    }


def _safe_partner(debt: Debt) -> Optional[Dict[str, Any]]:
    if debt.customer:
        c = debt.customer
        return {
            "id": c.customer_id,
            "name": c.customer_name,
            "phone_number": c.phone_number,
            "email": c.email,
            "address": c.address,
            "partner_type": "CUSTOMER",
            "sub_type": c.customer_type,
            "tax_code": None,
            "note": None,
        }
    if debt.supplier:
        s = debt.supplier
        return {
            "id": s.supplier_id,
            "name": s.supplier_name,
            "phone_number": s.phone_number,
            "email": s.email,
            "address": s.address,
            "partner_type": "SUPPLIER",
            "sub_type": s.product_group,
            "tax_code": s.tax_code,
            "note": s.note,
        }
    return None


def _serialize_debt_list_item(debt: Debt) -> Dict[str, Any]:
    orig = float(debt.original_amount) if debt.original_amount is not None else 0.0
    rem = float(debt.remaining_debt) if debt.remaining_debt is not None else 0.0
    paid = max(0.0, orig - rem)
    tx = debt.transaction

    return {
        "debt_id": debt.debt_id,
        "transaction_id": debt.transaction_id,
        "user_id": debt.user_id,
        "user": _safe_user(debt.user),
        "direction": str(debt.direction),
        "status": str(debt.status),
        "customer_id": debt.customer_id,
        "customer_name": debt.customer.customer_name if debt.customer else None,
        "supplier_id": debt.supplier_id,
        "supplier_name": debt.supplier.supplier_name if debt.supplier else None,
        "partner": _safe_partner(debt),
        "original_amount": orig,
        "paid_amount": paid,
        "remaining_debt": rem,
        "payment_count": len(debt.payments) if debt.payments else 0,
        "input_text": tx.input_text if tx else None,
        "note": tx.note if tx else None,
        "created_at": _safe_dt(debt.created_at),
        "updated_at": _safe_dt(debt.updated_at),
    }


def _serialize_payment(p: DebtPayment) -> Dict[str, Any]:
    acc = p.account
    return {
        "payment_id": p.payment_id,
        "debt_id": p.debt_id,
        "transaction_id": p.transaction_id,
        "account_id": p.account_id,
        "account": {
            "account_id": acc.account_id,
            "account_name": acc.account_name,
            "account_type": str(acc.account_type) if acc.account_type else None,
        } if acc else None,
        "amount": float(p.amount) if p.amount is not None else 0.0,
        "payment_percentage": float(p.payment_percentage) if p.payment_percentage is not None else None,
        "payment_date": _safe_dt(p.payment_date),
        "note": p.note,
        "created_at": _safe_dt(p.created_at),
    }


def _serialize_debt_detail(debt: Debt) -> Dict[str, Any]:
    data = _serialize_debt_list_item(debt)

    tx_info = None
    if debt.transaction:
        tx = debt.transaction
        details = []
        for d in (tx.transaction_detail or []):
            prod = d.product
            pname = d.product_name or (prod.product_name if prod else None)
            details.append({
                "detail_id": d.detail_id,
                "product_id": d.product_id,
                "product_name": pname,
                "quantity": float(d.quantity) if d.quantity is not None else 0.0,
                "unit": d.unit or "",
                "unit_price": float(d.unit_price) if d.unit_price is not None else 0.0,
                "subtotal": float(d.subtotal) if d.subtotal is not None else 0.0,
                "product": {
                    "product_id": prod.product_id,
                    "product_name": pname or prod.product_name,
                    "product_type": prod.product_type,
                    "default_unit": prod.default_unit,
                    "image": prod.img,
                } if prod else None,
            })
        intent_name = tx.intent.intent_name if tx.intent else None
        tx_info = {
            "transaction_id": tx.transaction_id,
            "transaction_date": _safe_dt(tx.transaction_date),
            "intent_name": intent_name,
            "intent_type": resolve_intent_type(tx.intent, intent_name),
            "input_method": tx.input_method,
            "input_text": tx.input_text,
            "note": tx.note,
            "total_amount": float(tx.total_amount) if tx.total_amount is not None else 0.0,
            "payment_status": str(tx.payment_status) if tx.payment_status else None,
            "details": details,
        }

    payments = sorted(
        debt.payments or [],
        key=lambda p: (p.payment_date or p.created_at or 0, p.payment_id or 0),
        reverse=True,
    )
    data["transaction"] = tx_info
    data["payments"] = [_serialize_payment(p) for p in payments]
    return data


def _resolve_sort_column(sort_by: str):
    mapping = {
        "created_at": Debt.created_at,
        "updated_at": Debt.updated_at,
        "original_amount": Debt.original_amount,
        "remaining_debt": Debt.remaining_debt,
        "debt_id": Debt.debt_id,
    }
    return mapping.get(sort_by, Debt.created_at)
