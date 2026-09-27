from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user_model import User
from app.models.inventory_model import InventoryTransaction
from app.models.transactionDetail_model import TransactionDetail


class InventoryStockRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_stock(self, user_id: int, product_id: int) -> Decimal:
        latest = (
            self.db.query(InventoryTransaction.quantity_after)
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id,
            )
            .order_by(InventoryTransaction.inventory_transaction_id.desc())
            .first()
        )
        return Decimal(str(latest[0])) if latest else Decimal("0.0")

    def get_inventory_history(
        self,
        user_id: int,
        product_id: int,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        types: Optional[List[str]] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        query = (
            self.db.query(InventoryTransaction)
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id
            )
        )

        if from_date:
            query = query.filter(InventoryTransaction.created_at >= from_date)
        if to_date:
            query = query.filter(InventoryTransaction.created_at <= to_date)
        if types:
            query = query.filter(InventoryTransaction.inventory_type.in_(types))

        total = query.count()
        offset = max(0, (page - 1) * limit)
        txs = (
            query.order_by(
                InventoryTransaction.created_at.desc(),
                InventoryTransaction.inventory_transaction_id.desc()
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        user = self.db.query(User).filter(User.user_id == user_id).first()
        user_name = user.full_name if user else "Hệ thống"

        items = []
        for tx in txs:
            note_display = tx.note or ""
            if tx.transaction_id and tx.transactions:
                t = tx.transactions
                if getattr(t, "customer", None) and t.customer:
                    note_display = f"Bán cho khách {t.customer.customer_name}" + (f": {tx.note}" if tx.note else "")
                elif getattr(t, "supplier", None) and t.supplier:
                    note_display = f"Nhập từ NCC {t.supplier.supplier_name}" + (f": {tx.note}" if tx.note else "")

            items.append({
                "inventory_transaction_id": tx.inventory_transaction_id,
                "inventory_type": tx.inventory_type,
                "quantity": float(tx.quantity),
                "quantity_before": float(tx.quantity_before),
                "quantity_after": float(tx.quantity_after),
                "note": note_display,
                "transaction_id": tx.transaction_id,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
                "created_by": user_name
            })

        return {
            "total": total,
            "items": items
        }

    def has_any_history(self, product_id: int) -> bool:
        has_td = (
            self.db.query(TransactionDetail.detail_id)
            .filter(TransactionDetail.product_id == product_id)
            .first()
            is not None
        )
        if has_td:
            return True

        has_it = (
            self.db.query(InventoryTransaction.inventory_transaction_id)
            .filter(InventoryTransaction.product_id == product_id)
            .first()
            is not None
        )
        return has_it
