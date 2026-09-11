import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from datetime import datetime, date
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session, joinedload
# pyrefly: ignore [missing-import]
from sqlalchemy import func, case, and_, or_, desc
# pyrefly: ignore [missing-import]
from fastapi import HTTPException, status

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.models.debt_model import Debt
from app.models.debt_payment_model import DebtPayment
from app.models.category_model import Category
from app.models.intent_model import Intent
from app.models.account_model import Account
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.models.closing_period_model import ClosingPeriod
from app.services.period_service import PeriodService

logger = logging.getLogger(__name__)


class ReportService:
    """
    Reporting Engine:
    - READ-ONLY: Tuyệt đối không thay đổi hay ghi dữ liệu vào database.
    - Pure SQL Aggregation: Sử dụng func.sum, func.count, group_by... thay vì load Python loops.
    - User Isolation: Tất cả truy vấn đều bắt buộc lọc theo user_id.
    """

    @classmethod
    def _check_period_closed(
        cls,
        db: Session,
        user_id: int,
        period_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Kiểm tra xem kỳ này đã được chốt (CLOSED) hay chưa.
        Chỉ lấy cờ is_closed và closing_id, KHÔNG lấy số liệu snapshot thay thế realtime.
        """
        p_type = period_info.get("period_type")
        p_start = period_info.get("period_start")
        p_end = period_info.get("period_end")

        if p_type in ["DAY", "MONTH", "QUARTER", "YEAR"]:
            closing = db.query(ClosingPeriod).filter(
                ClosingPeriod.user_id == user_id,
                ClosingPeriod.period_type == p_type,
                ClosingPeriod.period_start == p_start,
                ClosingPeriod.period_end == p_end,
                ClosingPeriod.status == "CLOSED"
            ).first()

            if closing:
                return {"is_closed": True, "closing_id": closing.closing_id}

        return {"is_closed": False, "closing_id": None}

    @classmethod
    def calculate_cogs(
        cls,
        db: Session,
        user_id: int,
        start_dt: datetime,
        end_dt: datetime
    ) -> Decimal:
        """
        Tính Giá vốn hàng bán (COGS):
        COGS = SUM(Số lượng bán ra * Giá tiền nhập hàng gần nhất của từng sản phẩm)
        """
        sales_details = db.query(
            TransactionDetail.product_id,
            func.sum(TransactionDetail.quantity).label("total_sold_qty")
        ).join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
         .join(Intent, Transaction.intent_id == Intent.intent_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "ban_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).group_by(TransactionDetail.product_id).all()

        total_cogs = Decimal("0.00")
        for prod_id, sold_qty in sales_details:
            if not prod_id or not sold_qty or sold_qty <= 0:
                continue

            # Tìm giá nhập gần nhất của sản phẩm này
            latest_purchase = db.query(TransactionDetail.unit_price)\
                .join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
                .join(Intent, Transaction.intent_id == Intent.intent_id)\
                .filter(
                    Transaction.user_id == user_id,
                    Intent.intent_name.in_(["mua_hang", "nhap_hang"]),
                    TransactionDetail.product_id == prod_id
                ).order_by(Transaction.transaction_date.desc()).first()

            cost_price = Decimal(str(latest_purchase[0])) if (latest_purchase and latest_purchase[0] is not None) else Decimal("0.00")
            total_cogs += Decimal(str(sold_qty)) * cost_price

        return total_cogs

    @classmethod
    def calculate_operating_expense(
        cls,
        db: Session,
        user_id: int,
        start_dt: datetime,
        end_dt: datetime
    ) -> Decimal:
        """
        Chi phí hoạt động (operating expense):
        Tiền điện, nước, mặt bằng, ship, văn phòng phẩm (intent = chi_tien hoặc Category type = EXPENSE, loại trừ mua hàng/trả nợ)
        """
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
    def get_live_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        GET /reports/live:
        Lấy số liệu realtime tổng hợp của kỳ (DAY, MONTH, QUARTER, YEAR hoặc custom).
        """
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        # 1. Tổng hợp từ bảng Transaction
        actual_paid = case(
            (Transaction.payment_status == "PENDING", 0),
            (
                Transaction.payment_status == "PARTIAL",
                case(
                    (Transaction.total_amount > func.coalesce(Debt.remaining_debt, 0), Transaction.total_amount - func.coalesce(Debt.remaining_debt, 0)),
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
                        (
                            and_(
                                or_(
                                    Intent.intent_type == "INCOME",
                                    Category.category_type == "INCOME",
                                    Intent.intent_name == "ban_hang"
                                ),
                                Intent.intent_name != "thu_no_khach_hang"
                            ),
                            case((Intent.intent_name == "ban_hang", Transaction.total_amount), else_=actual_paid)
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
                                    Intent.intent_type == "EXPENSE",
                                    Category.category_type == "EXPENSE",
                                    Intent.intent_name == "chi_tien"
                                ),
                                Intent.intent_name.notin_(["mua_hang", "nhap_hang", "tra_no_cung_cap", "tra_no_nha_cung_cap", "thu_no_nha_cung_cap"])
                            ),
                            Transaction.total_amount
                        ),
                        else_=0
                    )
                ), 0
            ).label("total_expense")
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
        total_expense = Decimal(str(tx_query.total_expense or 0))

        # 2. Công nợ thực tế từ bảng Debt
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

        # 3. Biến động kho từ Inventory_Transaction trong kỳ
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

        # 4. Tính COGS, Chi phí hoạt động & Lợi nhuận
        # Lợi nhuận = Doanh thu - Giá vốn (COGS) (số lượng * giá tiền nhập hàng) - Chi phí hoạt động
        # (Lợi nhuận có thể nhận giá trị âm nếu chi phí vượt doanh thu)
        cogs = cls.calculate_cogs(db, user_id, start_dt, end_dt)
        operating_expense = cls.calculate_operating_expense(db, user_id, start_dt, end_dt)
        profit = total_sales - cogs - operating_expense

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "summary": {
                "total_sales": total_sales,
                "total_purchase": total_purchase,
                "total_income": total_income,
                "total_expense": total_expense,
                "cogs": cogs,
                "operating_expense": operating_expense,
                "total_receivable": total_receivable,
                "total_payable": total_payable,
                "profit": profit
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
        """
        GET /reports/summary:
        Báo cáo tổng quan Dashboard: Doanh thu, Mua hàng, Chi phí, Lợi nhuận (Doanh thu - COGS - Chi phí hoạt động), Công nợ.
        """
        live_data = cls.get_live_report(db, user_id, period_params)
        summary = live_data["summary"]

        return {
            "period": live_data["period"],
            "revenue": {
                "total": summary["total_sales"] or summary["total_income"]
            },
            "purchase": {
                "total": summary["total_purchase"]
            },
            "expense": {
                "total": summary["total_expense"]
            },
            "profit": {
                "total": summary["profit"],
                "cogs": summary["cogs"],
                "operating_expense": summary["operating_expense"]
            },
            "debt": {
                "receivable": summary["total_receivable"],
                "payable": summary["total_payable"]
            }
        }

    @classmethod
    def get_sales_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        GET /reports/sales:
        Chỉ lấy giao dịch thuộc intent 'ban_hang'.
        Trả về total_sales, transaction_count, average_order_value, payment_status breakdown.
        """
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        # Aggregate tổng
        tx_query = db.query(
            func.count(Transaction.transaction_id).label("tx_count"),
            func.coalesce(func.sum(Transaction.total_amount), 0).label("total_sales")
        ).join(Intent, Transaction.intent_id == Intent.intent_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "ban_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).first()

        tx_count = tx_query.tx_count if tx_query else 0
        total_sales = Decimal(str(tx_query.total_sales or 0))
        avg_order = (total_sales / tx_count) if tx_count > 0 else Decimal("0.00")

        # Breakdown theo payment_status (PAID, PARTIAL, PENDING)
        status_query = db.query(
            Transaction.payment_status,
            func.coalesce(func.sum(Transaction.total_amount), 0).label("amount")
        ).join(Intent, Transaction.intent_id == Intent.intent_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "ban_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).group_by(Transaction.payment_status).all()

        payment_status_dict = {
            "PAID": Decimal("0.00"),
            "PARTIAL": Decimal("0.00"),
            "PENDING": Decimal("0.00")
        }
        for st, amt in status_query:
            if st in payment_status_dict:
                payment_status_dict[st] = Decimal(str(amt or 0))

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "total_sales": total_sales,
            "transaction_count": tx_count,
            "average_order_value": round(avg_order, 2),
            "payment_status": payment_status_dict
        }

    @classmethod
    def get_purchase_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        GET /reports/purchases:
        Intent: 'mua_hang'.
        Trả về total_purchase, transaction_count, breakdown theo supplier.
        """
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        tx_query = db.query(
            func.count(Transaction.transaction_id).label("tx_count"),
            func.coalesce(func.sum(Transaction.total_amount), 0).label("total_purchase")
        ).join(Intent, Transaction.intent_id == Intent.intent_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "mua_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).first()

        tx_count = tx_query.tx_count if tx_query else 0
        total_purchase = Decimal(str(tx_query.total_purchase or 0))

        # Breakdown theo Supplier
        supplier_query = db.query(
            Transaction.supplier_id,
            Supplier.supplier_name,
            func.count(Transaction.transaction_id).label("supplier_tx_count"),
            func.coalesce(func.sum(Transaction.total_amount), 0).label("supplier_amount")
        ).join(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Supplier, Transaction.supplier_id == Supplier.supplier_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "mua_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).group_by(Transaction.supplier_id, Supplier.supplier_name).all()

        suppliers = []
        for s_id, s_name, s_count, s_amt in supplier_query:
            suppliers.append({
                "supplier_id": s_id,
                "supplier_name": s_name or "Nhà cung cấp vãng lai",
                "total_amount": Decimal(str(s_amt or 0)),
                "transaction_count": s_count
            })

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "total_purchase": total_purchase,
            "transaction_count": tx_count,
            "suppliers": suppliers
        }

    @classmethod
    def get_expense_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        GET /reports/expenses:
        Intent: 'chi_tien' hoặc Category type = 'EXPENSE'.
        Trả về total_expense, categories breakdown.
        """
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

        # Breakdown theo Category
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
        """
        GET /reports/debts:
        Dựa vào bảng Debt, phân biệt RECEIVABLE và PAYABLE.
        """
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
        """
        GET /reports/inventory:
        Dựa trên Inventory_Transaction: IN, OUT, DAMAGE, ADJUSTMENT.
        """
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

    @classmethod
    def get_transactions_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any],
        intent_name: Optional[str] = None,
        category_id: Optional[int] = None,
        payment_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        GET /reports/transactions:
        Phân trang tại database với SQL LIMIT / OFFSET.
        """
        period = PeriodService.resolve_period(**period_params)
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        query = db.query(
            Transaction.transaction_id,
            Transaction.transaction_date,
            Intent.intent_name,
            Transaction.total_amount,
            Transaction.payment_status,
            Transaction.input_method,
            Transaction.note,
            Category.category_name,
            Customer.customer_name,
            Supplier.supplier_name
        ).outerjoin(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Category, Transaction.category_id == Category.category_id)\
         .outerjoin(Customer, Transaction.customer_id == Customer.customer_id)\
         .outerjoin(Supplier, Transaction.supplier_id == Supplier.supplier_id)\
         .filter(
             Transaction.user_id == user_id,
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         )

        if intent_name:
            query = query.filter(Intent.intent_name == intent_name)
        if category_id:
            query = query.filter(Transaction.category_id == category_id)
        if payment_status:
            query = query.filter(Transaction.payment_status == payment_status)

        total = query.count()
        offset = max(0, (page - 1) * page_size)
        rows = query.order_by(desc(Transaction.transaction_date)).offset(offset).limit(page_size).all()

        items = []
        for r in rows:
            items.append({
                "transaction_id": r.transaction_id,
                "transaction_date": r.transaction_date.isoformat() if r.transaction_date else "",
                "intent": r.intent_name,
                "total_amount": Decimal(str(r.total_amount or 0)),
                "payment_status": str(r.payment_status),
                "input_method": str(r.input_method) if r.input_method else None,
                "category_name": r.category_name,
                "customer_name": r.customer_name,
                "supplier_name": r.supplier_name,
                "note": r.note
            })

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total
        }

    @classmethod
    def get_transaction_detail(
        cls,
        db: Session,
        user_id: int,
        transaction_id: int
    ) -> Dict[str, Any]:
        """
        GET /reports/transactions/{id}:
        Lấy chi tiết giao dịch kèm các dòng hàng Transaction_Detail -> Product.
        Bắt buộc kiểm tra user ownership.
        """
        tx = db.query(Transaction)\
               .options(
                   joinedload(Transaction.intent),
                   joinedload(Transaction.category),
                   joinedload(Transaction.account),
                   joinedload(Transaction.customer),
                   joinedload(Transaction.supplier),
                   joinedload(Transaction.transaction_detail).joinedload(TransactionDetail.product)
               )\
               .filter(
                   Transaction.transaction_id == transaction_id,
                   Transaction.user_id == user_id
               ).first()

        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy giao dịch ID {transaction_id} hoặc bạn không có quyền truy cập."
            )

        details = []
        if tx.transaction_detail:
            dt_list = tx.transaction_detail if isinstance(tx.transaction_detail, list) else [tx.transaction_detail]
            for d in dt_list:
                details.append({
                    "detail_id": d.detail_id,
                    "product_id": d.product_id,
                    "product_name": d.product.product_name if d.product else "Sản phẩm không xác định",
                    "unit": d.unit or (d.product.default_unit if d.product else None),
                    "quantity": Decimal(str(d.quantity or 0)),
                    "unit_price": Decimal(str(d.unit_price or 0)),
                    "subtotal": Decimal(str(d.subtotal or 0))
                })

        return {
            "transaction_id": tx.transaction_id,
            "transaction_date": tx.transaction_date.isoformat() if tx.transaction_date else "",
            "intent": tx.intent.intent_name if tx.intent else None,
            "total_amount": Decimal(str(tx.total_amount or 0)),
            "payment_status": str(tx.payment_status),
            "input_method": str(tx.input_method) if tx.input_method else None,
            "note": tx.note,
            "account_id": tx.account_id,
            "account_name": tx.account.account_name if tx.account else None,
            "customer_id": tx.customer_id,
            "customer_name": tx.customer.customer_name if tx.customer else None,
            "supplier_id": tx.supplier_id,
            "supplier_name": tx.supplier.supplier_name if tx.supplier else None,
            "category_id": tx.category_id,
            "category_name": tx.category.category_name if tx.category else None,
            "details": details
        }
