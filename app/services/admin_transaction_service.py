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
from sqlalchemy import select, func, desc, or_, and_, case, cast, String

from app.models.debt_model import Debt

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.user_model import User
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.product_model import Product
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.services.transaction_service import resolve_intent_type, INTENT_TYPE_MAPPING
from app.utils.vn_search import vn_ilike


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
        group: Optional[str] = None,
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

        filters = dict(
            search=search, user_id=user_id, intent_name=intent_name, intent_type=intent_type,
            payment_status=payment_status, input_method=input_method,
            date_from=date_from, date_to=date_to, group=group,
        )
        stmt = _apply_filters(stmt, **filters)
        count_stmt = _apply_filters(count_stmt, **filters)

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
    # SUMMARY (cùng bộ lọc với danh sách, tính trên toàn bộ kết quả lọc)
    # =============================================
    @staticmethod
    def get_summary(
        db: Session,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        intent_name: Optional[str] = None,
        intent_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        input_method: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict:
        """
        Số liệu cho các thẻ KPI, tính trên toàn bộ kết quả lọc (không phân trang), theo cùng
        cách tách số của màn Báo cáo trên mobile (live_summary_report):
        doanh thu bán hàng, nhập hàng, chi phí vận hành, nợ phải thu / phải trả còn lại.
        Mỗi nhóm dùng đúng điều kiện của tham số `group` ở danh sách, nên bấm thẻ ra đúng các dòng đó.
        """
        filters = dict(
            search=search, user_id=user_id, intent_name=intent_name, intent_type=intent_type,
            payment_status=payment_status, input_method=input_method,
            date_from=date_from, date_to=date_to,
        )

        def total_of(cond):
            return func.coalesce(func.sum(case((cond, Transaction.total_amount), else_=0)), 0)

        stmt = select(
            func.count(Transaction.transaction_id),
            total_of(_type_is("INCOME")),
            total_of(_type_is("EXPENSE")),
            total_of(_group_condition("sales")),
            total_of(_group_condition("purchase")),
            total_of(_group_condition("expense")),
            total_of(Intent.intent_name.in_(DEBT_COLLECTION_INTENTS)),
        ).select_from(Transaction)
        row = db.execute(_apply_filters(stmt, **filters)).one()
        count, income, expense_all, sales, purchase, operating, collected = (float(v or 0) for v in row)

        # Công nợ còn lại: số dư hiện tại (không theo kỳ) của các cửa hàng có giao dịch khớp bộ lọc.
        user_ids = _apply_filters(select(Transaction.user_id).select_from(Transaction), **filters).distinct()
        debt_row = db.execute(
            select(
                func.coalesce(func.sum(case(
                    (and_(Debt.direction == "RECEIVABLE", Debt.status != "PAID"), Debt.remaining_debt),
                    else_=0,
                )), 0),
                func.coalesce(func.sum(case(
                    (and_(Debt.direction == "PAYABLE", Debt.status != "PAID"), Debt.remaining_debt),
                    else_=0,
                )), 0),
            ).filter(Debt.user_id.in_(user_ids))
        ).one()

        return {
            "total_count": int(count),
            "total_income": income,
            "total_expense": expense_all,
            "total_sales": sales,
            "total_purchase": purchase,
            "operating_expense": operating,
            "total_debt_collected": collected,
            "receivable_outstanding": float(debt_row[0] or 0),
            "payable_outstanding": float(debt_row[1] or 0),
            # Lãi tiền mặt = tiền thu vào - tiền chi ra (nhập hàng + chi phí)
            "net": income - expense_all,
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

# Nhóm intent khớp với cách mobile tách số (app/services/reports/live_summary_report.py)
PURCHASE_INTENTS = ["mua_hang", "nhap_hang"]
SALES_INTENTS = ["ban_hang"]
DEBT_COLLECTION_INTENTS = ["thu_no_khach_hang", "thu_no_phai_thu", "thu_no_khach"]
SUPPLIER_PAYMENT_INTENTS = ["tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"]
RECEIVABLE_INTENTS = ["ghi_no_khach_hang", "ghi_no_phai_thu", "khach_ghi_no", *DEBT_COLLECTION_INTENTS]
PAYABLE_INTENTS = [
    "ghi_no_nha_cung_cap", "ghi_no_cung_cap", "ghi_no_phai_tra", "ncc_ghi_no",
    "tra_no_cung_cap", "tra_no_nha_cung_cap", "tra_no_phai_tra", "tra_no_ncc", "thu_no_nha_cung_cap",
]
TRANSACTION_GROUPS = ("sales", "purchase", "expense", "receivable", "payable")


def _type_is(intent_type: str):
    """Loại giao dịch giống resolve_intent_type: lấy Intent.intent_type, null thì suy từ tên intent."""
    t = intent_type.strip().upper()
    fallback = [name for name, mapped in INTENT_TYPE_MAPPING.items() if mapped == t]
    return or_(
        func.upper(Intent.intent_type) == t,
        and_(Intent.intent_type.is_(None), Intent.intent_name.in_(fallback)),
    )


def _group_condition(group: str):
    """Điều kiện SQL của từng thẻ KPI — dùng chung cho lọc danh sách và summary."""
    if group == "sales":
        return Intent.intent_name.in_(SALES_INTENTS)
    if group == "purchase":
        return Intent.intent_name.in_(PURCHASE_INTENTS)
    if group == "expense":
        # Chi phí vận hành — cùng điều kiện operating_expense của mobile
        excluded = PURCHASE_INTENTS + SUPPLIER_PAYMENT_INTENTS
        return and_(
            or_(Intent.intent_name == "chi_tien", Category.category_type == "EXPENSE"),
            or_(Intent.intent_name.is_(None), Intent.intent_name.notin_(excluded)),
        )
    if group == "receivable":
        return Intent.intent_name.in_(RECEIVABLE_INTENTS)
    if group == "payable":
        return Intent.intent_name.in_(PAYABLE_INTENTS)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"group không hợp lệ. Chọn một trong: {', '.join(TRANSACTION_GROUPS)}",
    )


def _apply_filters(
    stmt,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    intent_name: Optional[str] = None,
    intent_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    input_method: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group: Optional[str] = None,
):
    """
    Áp bộ lọc admin lên một câu select có FROM là Transaction (dùng chung cho list / count / summary).
    Luôn outer join Intent + Category (quan hệ N-1, không nhân dòng) để các điều kiện nhóm dùng được.
    """
    stmt = (
        stmt.outerjoin(Intent, Transaction.intent_id == Intent.intent_id)
        .outerjoin(Category, Transaction.category_id == Category.category_id)
    )

    if user_id is not None:
        stmt = stmt.filter(Transaction.user_id == user_id)
    if intent_name:
        stmt = stmt.filter(Intent.intent_name.ilike(f"%{intent_name.strip()}%"))
    if intent_type:
        stmt = stmt.filter(_type_is(intent_type))
    if group:
        stmt = stmt.filter(_group_condition(group.strip().lower()))
    if payment_status:
        stmt = stmt.filter(Transaction.payment_status == payment_status.strip().upper())
    if input_method:
        stmt = stmt.filter(Transaction.input_method == input_method.strip().upper())
    if date_from:
        stmt = stmt.filter(Transaction.transaction_date >= date_from)
    if date_to:
        stmt = stmt.filter(Transaction.transaction_date <= date_to)

    # Search: transaction_id, input_text, note, user, store, customer, supplier, category, product (hỗ trợ không dấu)
    if search and search.strip():
        from app.models.store_model import Store

        term = search.strip()
        id_term = term.upper().replace("TX-", "").replace("#", "").strip()
        conditions = [
            vn_ilike(Transaction.input_text, term),
            vn_ilike(Transaction.note, term),
            cast(Transaction.transaction_id, String).ilike(f"%{term}%"),
            vn_ilike(Category.category_name, term),
        ]
        if id_term and id_term != term:
            conditions.append(cast(Transaction.transaction_id, String).ilike(f"%{id_term}%"))
        stmt = stmt.join(User, Transaction.user_id == User.user_id, isouter=True)
        conditions.extend([
            vn_ilike(User.full_name, term),
            User.email.ilike(f"%{term}%"),
            User.phone_number.ilike(f"%{term}%"),
            User.store_rel.has(vn_ilike(Store.store_name, term)),
            Transaction.customer.has(vn_ilike(Customer.customer_name, term)),
            Transaction.supplier.has(vn_ilike(Supplier.supplier_name, term)),
            Transaction.transaction_detail.any(vn_ilike(TransactionDetail.product_name, term)),
        ])
        stmt = stmt.filter(or_(*conditions))

    return stmt


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
        pname = d.product_name or (prod.product_name if prod else None)
        details.append({
            "detail_id": d.detail_id, "product_id": d.product_id,
            "product_name": pname,
            "quantity": float(d.quantity) if d.quantity is not None else 0.0,
            "unit": d.unit,
            "unit_price": float(d.unit_price) if d.unit_price is not None else 0.0,
            "subtotal": float(d.subtotal) if d.subtotal is not None else 0.0,
            "product": {
                "product_id": prod.product_id, "product_name": pname or prod.product_name,
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

