from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from fastapi import HTTPException, status

from app.models.transaction_model import Transaction
from app.models.transactionDetail_model import TransactionDetail
from app.models.category_model import Category
from app.models.intent_model import Intent
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.services.period_service import PeriodService
from app.services.reports.report_base import ReportBase


class TransactionReportMixin(ReportBase):
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
