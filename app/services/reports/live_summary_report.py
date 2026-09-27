from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from app.models.transaction_model import Transaction
from app.models.debt_model import Debt
from app.models.category_model import Category
from app.models.intent_model import Intent
from app.models.inventory_model import InventoryTransaction
from app.services.period_service import PeriodService
from app.services.reports.report_base import ReportBase


class LiveSummaryReportMixin(ReportBase):
    calculate_cogs: Any

    @classmethod
    def get_live_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]
        business_type = cls._get_user_business_type(db, user_id)

        actual_paid = case(
            (Transaction.payment_status == "PENDING", 0),
            (
                Transaction.payment_status == "PARTIAL",
                case(
                    (Transaction.total_amount > func.coalesce(Debt.remaining_debt, 0),
                     Transaction.total_amount - func.coalesce(Debt.remaining_debt, 0)),
                    else_=0
                )
            ),
            else_=Transaction.total_amount
        )

        tx_query = db.query(
            func.count(Transaction.transaction_id).label("tx_count"),
            func.coalesce(
                func.sum(
                    case((Intent.intent_name == "ban_hang", Transaction.total_amount), else_=0)
                ), 0
            ).label("total_sales"),
            func.coalesce(
                func.sum(
                    case((Intent.intent_name.in_(["mua_hang", "nhap_hang"]), Transaction.total_amount), else_=0)
                ), 0
            ).label("total_purchase"),
            func.coalesce(
                func.sum(
                    case(
                        (Intent.intent_name == "ban_hang", actual_paid),
                        (Intent.intent_name.in_(["thu_no_khach_hang", "thu_no_phai_thu", "thu_no_khach"]), Transaction.total_amount),
                        (
                            and_(
                                or_(
                                    Intent.intent_type == "INCOME",
                                    Category.category_type == "INCOME"
                                ),
                                Intent.intent_name.notin_(["ban_hang", "thu_no_khach_hang", "thu_no_phai_thu", "thu_no_khach"])
                            ),
                            Transaction.total_amount
                        ),
                        else_=0
                    )
                ), 0
            ).label("total_income"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                or_(
                                    Intent.intent_name == "chi_tien",
                                    and_(
                                        Category.category_type == "EXPENSE",
                                        Intent.intent_name.notin_([
                                            "mua_hang", "nhap_hang",
                                            "tra_no_cung_cap", "tra_no_nha_cung_cap"
                                        ])
                                    )
                                ),
                                Intent.intent_name.notin_([
                                    "mua_hang", "nhap_hang",
                                    "tra_no_cung_cap", "tra_no_nha_cung_cap",
                                    "thu_no_nha_cung_cap"
                                ])
                            ),
                            Transaction.total_amount
                        ),
                        else_=0
                    )
                ), 0
            ).label("operating_expense_raw"),
            func.coalesce(
                func.sum(
                    case(
                        (Intent.intent_name.in_(["mua_hang", "nhap_hang"]), actual_paid),
                        else_=0
                    )
                ), 0
            ).label("purchase_cash_paid"),
            func.coalesce(
                func.sum(
                    case(
                        (Intent.intent_name.in_(["tra_no_cung_cap", "tra_no_nha_cung_cap"]), Transaction.total_amount),
                        else_=0
                    )
                ), 0
            ).label("supplier_debt_paid")
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .outerjoin(Debt, Transaction.transaction_id == Debt.transaction_id)\
         .filter(
             Transaction.user_id == user_id,
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).first()

        tx_count = tx_query.tx_count if tx_query else 0
        total_sales = Decimal(str(tx_query.total_sales or 0))
        total_purchase = Decimal(str(tx_query.total_purchase or 0))
        total_income = Decimal(str(tx_query.total_income or 0))
        operating_expense_raw = Decimal(str(tx_query.operating_expense_raw or 0))
        purchase_cash_paid = Decimal(str(tx_query.purchase_cash_paid or 0))
        supplier_debt_paid = Decimal(str(tx_query.supplier_debt_paid or 0))

        operating_expense = operating_expense_raw
        total_expense = operating_expense
        total_cash_outflow = operating_expense_raw + purchase_cash_paid + supplier_debt_paid

        debt_query = db.query(
            func.coalesce(
                func.sum(
                    case(
                        (and_(Debt.direction == "RECEIVABLE", Debt.status != "PAID"), Debt.remaining_debt),
                        else_=0
                    )
                ), 0
            ).label("total_receivable"),
            func.coalesce(
                func.sum(
                    case(
                        (and_(Debt.direction == "PAYABLE", Debt.status != "PAID"), Debt.remaining_debt),
                        else_=0
                    )
                ), 0
            ).label("total_payable")
        ).filter(Debt.user_id == user_id).first()

        total_receivable = Decimal(str(debt_query.total_receivable or 0))
        total_payable = Decimal(str(debt_query.total_payable or 0))

        inv_query = db.query(
            func.coalesce(
                func.sum(case((InventoryTransaction.inventory_type == "IN", InventoryTransaction.quantity), else_=0)),
                0
            ).label("total_in"),
            func.coalesce(
                func.sum(case((InventoryTransaction.inventory_type == "OUT", InventoryTransaction.quantity), else_=0)),
                0
            ).label("total_out"),
            func.coalesce(
                func.sum(case((InventoryTransaction.inventory_type == "DAMAGE", InventoryTransaction.quantity), else_=0)),
                0
            ).label("total_damage"),
            func.coalesce(
                func.sum(case((InventoryTransaction.inventory_type == "ADJUSTMENT", InventoryTransaction.quantity), else_=0)),
                0
            ).label("total_adjustment")
        ).filter(
            InventoryTransaction.user_id == user_id,
            InventoryTransaction.created_at >= start_dt,
            InventoryTransaction.created_at <= end_dt
        ).first()

        total_in = Decimal(str(inv_query.total_in or 0))
        total_out = Decimal(str(inv_query.total_out or 0))
        total_damage = Decimal(str(inv_query.total_damage or 0))
        total_adjustment = Decimal(str(inv_query.total_adjustment or 0))

        cogs = cls.calculate_cogs(db, user_id, start_dt, end_dt, business_type)
        gross_profit = total_sales - cogs
        profit = total_sales - cogs - operating_expense
        cash_profit = total_income - total_cash_outflow

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "business_type": business_type,
            "summary": {
                "total_sales": total_sales,
                "total_purchase": total_purchase,
                "total_income": total_income,
                "total_expense": total_expense,
                "operating_expense": operating_expense,
                "purchase_cash_paid": purchase_cash_paid,
                "supplier_debt_paid": supplier_debt_paid,
                "total_cash_outflow": total_cash_outflow,
                "cogs": cogs,
                "total_receivable": total_receivable,
                "total_payable": total_payable,
                "gross_profit": gross_profit,
                "profit": profit,
                "cash_profit": cash_profit
            },
            "transaction_count": tx_count,
            "inventory": {
                "total_in": total_in,
                "total_out": total_out,
                "total_damage": total_damage,
                "total_adjustment": total_adjustment
            }
        }

    @classmethod
    def get_summary_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        live_data = cls.get_live_report(db, user_id, period_params)
        summary = live_data["summary"]
        business_type = live_data.get("business_type", "RESELLER")

        return {
            "period": live_data["period"],
            "business_type": business_type,
            "revenue": {
                "total": summary["total_sales"]
            },
            "purchase": {
                "total": summary["total_purchase"],
                "cash_paid": summary["purchase_cash_paid"]
            },
            "expense": {
                "total": summary["operating_expense"],
                "operating": summary["operating_expense"],
                "supplier_debt_paid": summary["supplier_debt_paid"]
            },
            "profit": {
                "total": summary["profit"],
                "gross_profit": summary.get("gross_profit", summary["total_sales"] - summary["cogs"]),
                "cogs": summary["cogs"],
                "operating_expense": summary["operating_expense"],
                "cash_profit": summary["cash_profit"]
            },
            "debt": {
                "receivable": summary["total_receivable"],
                "payable": summary["total_payable"]
            }
        }
