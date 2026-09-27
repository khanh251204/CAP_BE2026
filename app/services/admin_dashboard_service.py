"""
Admin Dashboard — Service Layer

Pure SQL database aggregations for Web Admin KPIs, financial trends,
top performing products, and expense category breakdown.
"""
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.product_model import Product
from app.models.user_model import User
from app.models.intent_model import Intent
from app.models.category_model import Category
from app.models.debt_model import Debt
from app.services.period_service import PeriodService


class AdminDashboardService:

    @staticmethod
    def get_summary(
        db: Session,
        period_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        period = PeriodService.resolve_period(
            period_type=period_type,
            from_date=from_date,
            to_date=to_date
        )
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        # === 1. Revenue, Expense, Purchase, Tx Count ===
        filter_exp = and_(
            or_(Intent.intent_name == "chi_tien", Category.category_type == "EXPENSE"),
            Intent.intent_name.notin_([
                "mua_hang", "nhap_hang", "tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"
            ])
        )

        tx_query = db.query(
            func.count(Transaction.transaction_id).label("tx_count"),
            func.coalesce(
                func.sum(case((Intent.intent_name == "ban_hang", Transaction.total_amount), else_=0)), 0
            ).label("revenue"),
            func.coalesce(
                func.sum(case((Intent.intent_name.in_(["mua_hang", "nhap_hang"]), Transaction.total_amount), else_=0)), 0
            ).label("purchase"),
            func.coalesce(
                func.sum(case((filter_exp, Transaction.total_amount), else_=0)), 0
            ).label("expense")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .filter(
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         )

        if user_id is not None:
            tx_query = tx_query.filter(Transaction.user_id == user_id)

        tx_res = tx_query.first()
        revenue = float(tx_res.revenue or 0) if tx_res else 0.0
        expense = float(tx_res.expense or 0) if tx_res else 0.0
        purchase = float(tx_res.purchase or 0) if tx_res else 0.0
        tx_count = int(tx_res.tx_count or 0) if tx_res else 0
        profit = revenue - expense

        # === 2. Active Debt (Receivable & Payable) ===
        debt_query = db.query(
            func.coalesce(
                func.sum(case((and_(Debt.direction == "RECEIVABLE", Debt.status != "PAID"), Debt.remaining_debt), else_=0)), 0
            ).label("receivable"),
            func.coalesce(
                func.sum(case((and_(Debt.direction == "PAYABLE", Debt.status != "PAID"), Debt.remaining_debt), else_=0)), 0
            ).label("payable")
        )

        if user_id is not None:
            debt_query = debt_query.filter(Debt.user_id == user_id)

        debt_res = debt_query.first()
        receivable = float(debt_res.receivable or 0) if debt_res else 0.0
        payable = float(debt_res.payable or 0) if debt_res else 0.0

        # === 3. System User Count & Product Count ===
        user_count_q = db.query(func.count(User.user_id))
        if user_id is not None:
            user_count_q = user_count_q.filter(User.user_id == user_id)
        user_count = user_count_q.scalar() or 0

        prod_count_q = db.query(func.count(Product.product_id))
        if user_id is not None:
            prod_count_q = prod_count_q.filter(Product.user_id == user_id)
        prod_count = prod_count_q.scalar() or 0

        return {
            "period": {
                "period_type": period["period_type"],
                "start": period["start_datetime"].isoformat(),
                "end": period["end_datetime"].isoformat(),
            },
            "summary": {
                "revenue": revenue,
                "expense": expense,
                "profit": profit,
                "purchase": purchase,
                "receivable": receivable,
                "payable": payable,
                "transaction_count": tx_count,
                "user_count": user_count,
                "product_count": prod_count,
            }
        }

    @staticmethod
    def get_trends(
        db: Session,
        period_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        period = PeriodService.resolve_period(
            period_type=period_type,
            from_date=from_date,
            to_date=to_date
        )
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        filter_exp = and_(
            or_(Intent.intent_name == "chi_tien", Category.category_type == "EXPENSE"),
            Intent.intent_name.notin_([
                "mua_hang", "nhap_hang", "tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"
            ])
        )

        date_col = func.date(Transaction.transaction_date)

        trend_query = db.query(
            date_col.label("tx_date"),
            func.count(Transaction.transaction_id).label("tx_count"),
            func.coalesce(
                func.sum(case((Intent.intent_name == "ban_hang", Transaction.total_amount), else_=0)), 0
            ).label("revenue"),
            func.coalesce(
                func.sum(case((filter_exp, Transaction.total_amount), else_=0)), 0
            ).label("expense")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .filter(
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         )

        if user_id is not None:
            trend_query = trend_query.filter(Transaction.user_id == user_id)

        rows = trend_query.group_by(date_col).order_by(date_col.asc()).all()

        results = []
        for r_date, r_count, r_rev, r_exp in rows:
            rev = float(r_rev or 0)
            exp = float(r_exp or 0)
            results.append({
                "date": str(r_date),
                "revenue": rev,
                "expense": exp,
                "profit": rev - exp,
                "transaction_count": int(r_count or 0),
            })
        return results

    @staticmethod
    def get_top_products(
        db: Session,
        period_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 5,
        sort_by: str = "revenue",
    ) -> List[Dict[str, Any]]:
        period = PeriodService.resolve_period(
            period_type=period_type,
            from_date=from_date,
            to_date=to_date
        )
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        query = db.query(
            TransactionDetail.product_id,
            Product.product_name,
            TransactionDetail.unit,
            func.coalesce(func.sum(TransactionDetail.quantity), 0).label("qty_sold"),
            func.coalesce(func.sum(TransactionDetail.subtotal), 0).label("revenue")
        ).join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
         .join(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Product, TransactionDetail.product_id == Product.product_id)\
         .filter(
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt,
             Intent.intent_name == "ban_hang"
         )

        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)

        query = query.group_by(
            TransactionDetail.product_id, Product.product_name, TransactionDetail.unit
        )

        if sort_by == "quantity":
            query = query.order_by(func.sum(TransactionDetail.quantity).desc())
        else:
            query = query.order_by(func.sum(TransactionDetail.subtotal).desc())

        rows = query.limit(limit).all()

        results = []
        for p_id, p_name, p_unit, qty, rev in rows:
            results.append({
                "product_id": p_id or 0,
                "product_name": p_name or (f"Sản phẩm #{p_id}" if p_id else "Khác"),
                "unit": p_unit or "",
                "quantity_sold": float(qty or 0),
                "revenue": float(rev or 0),
            })
        return results

    @staticmethod
    def get_expense_categories(
        db: Session,
        period_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        period = PeriodService.resolve_period(
            period_type=period_type,
            from_date=from_date,
            to_date=to_date
        )
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        filter_exp = and_(
            or_(Intent.intent_name == "chi_tien", Category.category_type == "EXPENSE"),
            Intent.intent_name.notin_([
                "mua_hang", "nhap_hang", "tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"
            ])
        )

        query = db.query(
            Transaction.category_id,
            Category.category_name,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("amount")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .filter(
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt,
             filter_exp
         )

        if user_id is not None:
            query = query.filter(Transaction.user_id == user_id)

        rows = query.group_by(Transaction.category_id, Category.category_name)\
                    .order_by(func.sum(Transaction.total_amount).desc()).all()

        results = []
        for c_id, c_name, amt in rows:
            results.append({
                "category_id": c_id,
                "category_name": c_name or "Chi phí khác",
                "amount": float(amt or 0),
            })
        return results
