"""
Admin Transaction Management — Service Layer

Reuse TransactionRepository cho query cơ bản.
Mở rộng: query cross-user (không filter user_id), search, filter nâng cao.
Không tạo model/bảng mới. Chỉ đọc dữ liệu hiện tại.
"""
from math import ceil
from typing import Optional, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, desc, or_, cast, String

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.user_model import User
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.product_model import Product
from app.services.transaction_service import resolve_intent_type


class AdminTransactionService:

    # =============================================
    # LIST TRANSACTIONS (cross-user, all filters)
    # =============================================
    @staticmethod
    def list_transactions(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        intent_name: Optional[str] = None,
        intent_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        input_method: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict:
        # === Base query with eager loading ===
        stmt = (
            select(Transaction)
            .options(
                joinedload(Transaction.user),
                joinedload(Transaction.intent),
                joinedload(Transaction.category),
                joinedload(Transaction.account),
                joinedload(Transaction.customer),
                joinedload(Transaction.supplier),
                joinedload(Transaction.transaction_detail)
                    .joinedload(TransactionDetail.product),
            )
        )
        count_stmt = select(func.count()).select_from(Transaction)

        # --- JOIN flags to prevent duplicate joins ---
        intent_joined = False
        user_joined = False

        # === Filter: user_id ===
        if user_id is not None:
            stmt = stmt.filter(Transaction.user_id == user_id)
            count_stmt = count_stmt.filter(Transaction.user_id == user_id)

        # === Filter: intent_name (exact match, case-insensitive) ===
        if intent_name:
            stmt = stmt.join(Transaction.intent)
            count_stmt = count_stmt.join(Transaction.intent)
            intent_joined = True
            stmt = stmt.filter(
                Intent.intent_name.ilike(f"%{intent_name.strip()}%")
            )
            count_stmt = count_stmt.filter(
                Intent.intent_name.ilike(f"%{intent_name.strip()}%")
            )

        # === Filter: intent_type ===
        if intent_type:
            if not intent_joined:
                stmt = stmt.join(Transaction.intent)
                count_stmt = count_stmt.join(Transaction.intent)
                intent_joined = True
            stmt = stmt.filter(
                func.upper(Intent.intent_type) == intent_type.strip().upper()
            )
            count_stmt = count_stmt.filter(
                func.upper(Intent.intent_type) == intent_type.strip().upper()
            )

        # === Filter: payment_status ===
        if payment_status:
            val = payment_status.strip().upper()
            stmt = stmt.filter(Transaction.payment_status == val)
            count_stmt = count_stmt.filter(Transaction.payment_status == val)

        # === Filter: input_method ===
        if input_method:
            val = input_method.strip().upper()
            stmt = stmt.filter(Transaction.input_method == val)
            count_stmt = count_stmt.filter(Transaction.input_method == val)

        # === Filter: date range ===
        if date_from:
            stmt = stmt.filter(Transaction.transaction_date >= date_from)
            count_stmt = count_stmt.filter(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.filter(Transaction.transaction_date <= date_to)
            count_stmt = count_stmt.filter(Transaction.transaction_date <= date_to)

        # === Search: transaction_id, input_text, note, user name/email ===
        if search:
            term = search.strip()
            search_conditions = [
                Transaction.input_text.ilike(f"%{term}%"),
                Transaction.note.ilike(f"%{term}%"),
                cast(Transaction.transaction_id, String).ilike(f"%{term}%"),
            ]
            # Join User for search on user fields
            if not user_joined:
                stmt = stmt.join(Transaction.user, isouter=True)
                count_stmt = count_stmt.join(User, Transaction.user_id == User.user_id, isouter=True)
                user_joined = True
            search_conditions.extend([
                User.full_name.ilike(f"%{term}%"),
                User.email.ilike(f"%{term}%"),
                User.store_name.ilike(f"%{term}%"),
            ])
            stmt = stmt.filter(or_(*search_conditions))
            count_stmt = count_stmt.filter(or_(*search_conditions))

        # === Count total ===
        total = db.scalar(count_stmt) or 0

        # === Sorting ===
        sort_col = _resolve_sort_column(sort_by)
        order_fn = desc if sort_order.lower() == "desc" else lambda c: c.asc()
        stmt = stmt.order_by(order_fn(sort_col), desc(Transaction.transaction_id))

        # === Pagination ===
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        transactions = db.scalars(stmt).unique().all()
        total_pages = ceil(total / limit) if limit > 0 else 0

        # === Serialize ===
        items = [_serialize_transaction_list_item(tx) for tx in transactions]

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        }

    # =============================================
    # GET TRANSACTION DETAIL (by ID, cross-user)
    # =============================================
    @staticmethod
    def get_transaction_detail(
        db: Session,
        transaction_id: int,
    ) -> Dict:
        stmt = (
            select(Transaction)
            .options(
                joinedload(Transaction.user),
                joinedload(Transaction.intent),
                joinedload(Transaction.category),
                joinedload(Transaction.account),
                joinedload(Transaction.customer),
                joinedload(Transaction.supplier),
                joinedload(Transaction.transaction_detail)
                    .joinedload(TransactionDetail.product),
            )
            .filter(Transaction.transaction_id == transaction_id)
        )
        transaction = db.scalars(stmt).unique().first()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy giao dịch với ID {transaction_id}"
            )

        return _serialize_transaction_detail(transaction)

# ========================================
# Private helpers
# ========================================

def _safe_dt(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _safe_user(user) -> Optional[Dict]:
    if not user:
        return None
    return {
        "user_id": user.user_id, "full_name": user.full_name,
        "email": user.email, "phone_number": user.phone_number,
        "business_type": user.business_type, "store_name": user.store_name,
        "role": user.role,
    }


def _safe_account(acct) -> Optional[Dict]:
    if not acct:
        return None
    return {"account_id": acct.account_id, "account_name": acct.account_name, "account_type": acct.account_type}


def _safe_partner(p, kind: str) -> Optional[Dict]:
    if not p:
        return None
    if kind == "customer":
        return {"id": p.customer_id, "name": p.customer_name, "phone_number": p.phone_number}
    return {"id": p.supplier_id, "name": p.supplier_name, "phone_number": p.phone_number}


def _safe_category(cat) -> Optional[Dict]:
    if not cat:
        return None
    return {"category_id": cat.category_id, "category_name": cat.category_name, "category_type": cat.category_type}


def _tx_base(tx) -> Dict:
    """Common transaction fields shared between list and detail responses."""
    intent_name = tx.intent.intent_name if tx.intent else None
    return {
        "transaction_id": tx.transaction_id, "user_id": tx.user_id,
        "user": _safe_user(tx.user),
        "intent_id": tx.intent_id, "intent_name": intent_name,
        "intent_type": resolve_intent_type(tx.intent, intent_name),
        "category_id": tx.category_id, "category": _safe_category(tx.category),
        "account_id": tx.account_id, "account": _safe_account(tx.account),
        "customer_id": tx.customer_id, "customer": _safe_partner(tx.customer, "customer"),
        "supplier_id": tx.supplier_id, "supplier": _safe_partner(tx.supplier, "supplier"),
        "total_amount": float(tx.total_amount) if tx.total_amount is not None else 0.0,
        "payment_status": tx.payment_status, "input_method": tx.input_method,
        "input_text": tx.input_text, "note": tx.note,
        "transaction_date": _safe_dt(tx.transaction_date),
        "created_at": _safe_dt(tx.created_at), "updated_at": _safe_dt(tx.updated_at),
    }


def _serialize_transaction_list_item(tx) -> Dict:
    data = _tx_base(tx)
    data["detail_count"] = len(tx.transaction_detail) if tx.transaction_detail else 0
    return data


def _serialize_transaction_detail(tx) -> Dict:
    data = _tx_base(tx)
    details = []
    for d in (tx.transaction_detail or []):
        prod = d.product
        details.append({
            "detail_id": d.detail_id, "product_id": d.product_id,
            "quantity": float(d.quantity) if d.quantity is not None else 0.0,
            "unit": d.unit,
            "unit_price": float(d.unit_price) if d.unit_price is not None else 0.0,
            "subtotal": float(d.subtotal) if d.subtotal is not None else 0.0,
            "product": {
                "product_id": prod.product_id, "product_name": prod.product_name,
                "product_type": prod.product_type, "default_unit": prod.default_unit,
                "image": prod.img,
            } if prod else None,
        })
    data["details"] = details
    return data


def _resolve_sort_column(sort_by: str):
    mapping = {
        "created_at": Transaction.created_at,
        "transaction_date": Transaction.transaction_date,
        "total_amount": Transaction.total_amount,
        "transaction_id": Transaction.transaction_id,
    }
    return mapping.get(sort_by, Transaction.created_at)

