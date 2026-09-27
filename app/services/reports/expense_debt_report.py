from decimal import Decimal
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from app.models.transaction_model import Transaction
from app.models.category_model import Category
from app.models.intent_model import Intent
from app.models.debt_model import Debt
from app.models.inventory_model import InventoryTransaction
from app.services.period_service import PeriodService
from app.services.reports.report_base import ReportBase


class ExpenseDebtReportMixin(ReportBase):
    @classmethod
    def calculate_operating_expense(
        cls,
        db: Session,
        user_id: int,
        start_dt: datetime,
        end_dt: datetime
    ) -> Decimal:
        op_query = db.query(
            func.coalesce(func.sum(Transaction.total_amount), 0).label("op_expense")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .filter(
             Transaction.user_id == user_id,
             or_(
                 Intent.intent_name == "chi_tien",
                 Category.category_type == "EXPENSE"
             ),
             Intent.intent_name.notin_(["mua_hang", "nhap_hang", "tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"]),
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).first()

        return Decimal(str(op_query.op_expense or 0)) if op_query else Decimal("0.00")

    @classmethod
    def get_expense_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        filter_exp = and_(
            or_(
                Intent.intent_name == "chi_tien",
                Category.category_type == "EXPENSE"
            ),
            Intent.intent_name.notin_(["mua_hang", "nhap_hang", "tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"])
        )

        total_query = db.query(
            func.coalesce(func.sum(Transaction.total_amount), 0).label("total_expense")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .filter(
             Transaction.user_id == user_id,
             filter_exp,
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).first()

        total_expense = Decimal(str(total_query.total_expense or 0)) if total_query else Decimal("0.00")

        cat_query = db.query(
            Transaction.category_id,
            Category.category_name,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("cat_amount")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .filter(
             Transaction.user_id == user_id,
             filter_exp,
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).group_by(Transaction.category_id, Category.category_name).all()

        categories = []
        for c_id, c_name, c_amt in cat_query:
            categories.append({
                "category_id": c_id,
                "category_name": c_name or "Chi phí khác",
                "amount": Decimal(str(c_amt or 0))
            })

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "total_expense": total_expense,
            "categories": categories
        }

    @classmethod
    def get_debt_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        query = db.query(
            Debt.direction,
            func.coalesce(func.sum(Debt.original_amount), 0).label("orig_amt"),
            func.coalesce(
                func.sum(case((Debt.status != "PAID", Debt.remaining_debt), else_=0)),
                0
            ).label("rem_amt")
        ).filter(Debt.user_id == user_id).group_by(Debt.direction).all()

        rec = {"original_amount": Decimal("0.00"), "remaining": Decimal("0.00")}
        pay = {"original_amount": Decimal("0.00"), "remaining": Decimal("0.00")}

        for direction, orig, rem in query:
            if direction == "RECEIVABLE":
                rec["original_amount"] = Decimal(str(orig or 0))
                rec["remaining"] = Decimal(str(rem or 0))
            elif direction == "PAYABLE":
                pay["original_amount"] = Decimal(str(orig or 0))
                pay["remaining"] = Decimal(str(rem or 0))

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "receivable": rec,
            "payable": pay
        }

    @classmethod
    def get_inventory_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        query = db.query(
            InventoryTransaction.inventory_type,
            func.coalesce(func.sum(InventoryTransaction.quantity), 0).label("total_qty")
        ).filter(
            InventoryTransaction.user_id == user_id,
            InventoryTransaction.created_at >= start_dt,
            InventoryTransaction.created_at <= end_dt
        ).group_by(InventoryTransaction.inventory_type).all()

        inv_map = {
            "IN": Decimal("0.00"),
            "OUT": Decimal("0.00"),
            "DAMAGE": Decimal("0.00"),
            "ADJUSTMENT": Decimal("0.00")
        }
        for itype, qty in query:
            if itype in inv_map:
                inv_map[itype] = Decimal(str(qty or 0))

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "total_in": inv_map["IN"],
            "total_out": inv_map["OUT"],
            "total_damage": inv_map["DAMAGE"],
            "total_adjustment": inv_map["ADJUSTMENT"]
        }
