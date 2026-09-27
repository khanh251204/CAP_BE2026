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

        sales_rows = db.query(
            TransactionDetail.product_id,
            Product.product_name,
            TransactionDetail.unit,
            func.sum(TransactionDetail.quantity).label("total_sold_qty"),
            func.sum(TransactionDetail.subtotal).label("total_revenue")
        ).join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
         .join(Intent, Transaction.intent_id == Intent.intent_id)\
         .outerjoin(Product, TransactionDetail.product_id == Product.product_id)\
         .filter(
             Transaction.user_id == user_id,
             Intent.intent_name == "ban_hang",
             Transaction.transaction_date >= start_dt,
             Transaction.transaction_date <= end_dt
         ).group_by(
             TransactionDetail.product_id,
             Product.product_name,
             TransactionDetail.unit
         ).all()

        results = []
        for prod_id, prod_name, unit, sold_qty, revenue in sales_rows:
            sold_qty_dec = Decimal(str(sold_qty or 0))
            rev_dec = Decimal(str(revenue or 0))
            cost_price = Decimal("0.00")

            if bt != "SERVICE" and prod_id:
                latest_p = db.query(TransactionDetail.unit_price)\
                    .join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
                    .join(Intent, Transaction.intent_id == Intent.intent_id)\
                    .filter(
                        Transaction.user_id == user_id,
                        Intent.intent_name.in_(["mua_hang", "nhap_hang"]),
                        TransactionDetail.product_id == prod_id,
                        Transaction.transaction_date <= end_dt
                    ).order_by(Transaction.transaction_date.desc(), TransactionDetail.detail_id.desc()).first()

                if not latest_p or latest_p[0] is None:
                    latest_p = db.query(TransactionDetail.unit_price)\
                        .join(Transaction, TransactionDetail.transaction_id == Transaction.transaction_id)\
                        .join(Intent, Transaction.intent_id == Intent.intent_id)\
                        .filter(
                            Transaction.user_id == user_id,
                            Intent.intent_name.in_(["mua_hang", "nhap_hang"]),
                            TransactionDetail.product_id == prod_id
                        ).order_by(Transaction.transaction_date.desc(), TransactionDetail.detail_id.desc()).first()

                if latest_p and latest_p[0] is not None:
                    cost_price = Decimal(str(latest_p[0]))

            prod_cogs = sold_qty_dec * cost_price
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
