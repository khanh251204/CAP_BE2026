import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.product_model import Product
from app.models.intent_model import Intent
from app.models.supplier_model import Supplier
from app.services.period_service import PeriodService
from app.services.reports.report_base import ReportBase
from app.services.reports.fifo_cost import fifo_sale_costs, latest_purchase_price

logger = logging.getLogger(__name__)


class SalesPurchaseReportMixin(ReportBase):
    @classmethod
    def get_product_sales_breakdown(
        cls,
        db: Session,
        user_id: int,
        start_dt: datetime,
        end_dt: datetime,
        business_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        bt = (business_type or cls._get_user_business_type(db, user_id)).upper()

        # Từng dòng bán trong kỳ (giữ transaction_id để gắn giá vốn FIFO của đúng lần xuất kho)
        sale_rows = db.query(
            TransactionDetail.transaction_id,
            TransactionDetail.product_id,
            func.coalesce(TransactionDetail.product_name, Product.product_name).label("product_name"),
            TransactionDetail.unit,
            TransactionDetail.quantity,
            TransactionDetail.subtotal,
        ).join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
         .join(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Product, TransactionDetail.product_id == Product.product_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "ban_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).all()

        with_cost = bt != "SERVICE"
        fifo = fifo_sale_costs(db, user_id, (r.product_id for r in sale_rows)) if with_cost else {}

        # Tổng SL bán của mỗi (giao dịch, sản phẩm) — chia giá vốn khi 1 giao dịch có nhiều dòng cùng sản phẩm
        tx_qty: Dict[tuple, Decimal] = {}
        for r in sale_rows:
            key = (r.transaction_id, r.product_id)
            tx_qty[key] = tx_qty.get(key, Decimal("0")) + Decimal(str(r.quantity or 0))

        groups: Dict[tuple, Dict[str, Any]] = {}
        fallback_price: Dict[int, Decimal] = {}
        for r in sale_rows:
            qty = Decimal(str(r.quantity or 0))
            g = groups.setdefault((r.product_id, r.product_name, r.unit), {
                "qty": Decimal("0"), "revenue": Decimal("0"), "cogs": Decimal("0"),
            })
            g["qty"] += qty
            g["revenue"] += Decimal(str(r.subtotal or 0))
            if not (with_cost and r.product_id):
                continue

            key = (r.transaction_id, r.product_id)
            total_qty = tx_qty[key]
            share = qty / total_qty if total_qty > 0 else Decimal("0")
            fifo_qty, fifo_cost = fifo.get(key, (Decimal("0"), Decimal("0")))
            g["cogs"] += fifo_cost * share
            # Phần bán không qua sổ kho (vd: thành phẩm bán khi tồn = 0) -> giá nhập gần nhất
            uncovered = max(total_qty - fifo_qty, Decimal("0")) * share
            if uncovered > 0:
                if r.product_id not in fallback_price:
                    fallback_price[r.product_id] = latest_purchase_price(db, user_id, r.product_id, end_dt)
                g["cogs"] += uncovered * fallback_price[r.product_id]

        results = []
        for (prod_id, prod_name, unit), g in groups.items():
            sold_qty_dec = g["qty"]
            rev_dec = g["revenue"]
            prod_cogs = g["cogs"].quantize(Decimal("0.01"))
            # Giá vốn bình quân / đơn vị của lượng đã bán (FIFO)
            cost_price = (prod_cogs / sold_qty_dec).quantize(Decimal("0.01")) if sold_qty_dec > 0 else Decimal("0.00")
            gross_profit = rev_dec - prod_cogs

            results.append({
                "product_id": prod_id,
                "product_name": prod_name or (f"Sản phẩm #{prod_id}" if prod_id else "Mặt hàng khác"),
                "quantity_sold": sold_qty_dec,
                "unit": unit or "",
                "revenue": rev_dec,
                "cost_price": cost_price,
                "cogs": prod_cogs,
                "gross_profit": gross_profit
            })

        return results

    @classmethod
    def calculate_cogs(
        cls,
        db: Session,
        user_id: int,
        start_dt: datetime,
        end_dt: datetime,
        business_type: Optional[str] = None
    ) -> Decimal:
        bt = (business_type or cls._get_user_business_type(db, user_id)).upper()
        if bt == "SERVICE":
            return Decimal("0.00")

        product_breakdown = cls.get_product_sales_breakdown(db, user_id, start_dt, end_dt, bt)
        total_prod_cogs = sum(item["cogs"] for item in product_breakdown)

        # Giá vốn chỉ phát sinh khi có bán hàng: chưa bán thì tiền nhập hàng là hàng tồn kho, không phải giá vốn
        if not product_breakdown:
            return Decimal("0.00")

        if bt == "PRODUCER":
            if total_prod_cogs > 0:
                return total_prod_cogs
            purchase_result = db.query(
                func.coalesce(func.sum(Transaction.total_amount), 0).label("total_purchase")
            ).join(Intent, Transaction.intent_id == Intent.intent_id)\
             .filter(
                 Transaction.user_id == user_id,
                 Intent.intent_name.in_(["mua_hang", "nhap_hang"]),
                 Transaction.transaction_date >= start_dt,
                 Transaction.transaction_date <= end_dt
             ).first()
            return Decimal(str(purchase_result.total_purchase or 0)) if purchase_result else Decimal("0.00")

        return Decimal(str(total_prod_cogs))

    @classmethod
    def get_sales_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        period = PeriodService.resolve_period(**period_params)
        closed_status = cls._check_period_closed(db, user_id, period)

        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

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

        business_type = cls._get_user_business_type(db, user_id)
        products_breakdown = cls.get_product_sales_breakdown(db, user_id, start_dt, end_dt, business_type)
        cogs = sum(item["cogs"] for item in products_breakdown)
        gross_profit = total_sales - cogs

        return {
            "period": {
                "type": period["period_type"],
                "start": period["period_start"].isoformat(),
                "end": period["period_end"].isoformat(),
                "is_closed": closed_status["is_closed"],
                "closing_id": closed_status["closing_id"]
            },
            "total_sales": total_sales,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "transaction_count": tx_count,
            "average_order_value": round(avg_order, 2),
            "payment_status": payment_status_dict,
            "products": products_breakdown
        }

    @classmethod
    def get_purchase_report(
        cls,
        db: Session,
        user_id: int,
        period_params: Dict[str, Any]
    ) -> Dict[str, Any]:
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
