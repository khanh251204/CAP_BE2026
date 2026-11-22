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

    def get_latest_stock(self, user_id: int, product_id: int, for_update: bool = False) -> Decimal:
        """
        for_update=True: đọc có khoá (SELECT ... FOR UPDATE) -> luôn thấy tồn mới nhất đã commit.
        Dùng trong các hàm GHI kho sau lock_product: MySQL/TiDB mặc định REPEATABLE READ, đọc thường
        sau khi chờ khoá vẫn thấy ảnh chụp cũ nên 2 đơn cùng lúc có thể cùng thấy "còn hàng".
        """
        query = (
            self.db.query(InventoryTransaction.quantity_after)
            .filter(
                InventoryTransaction.user_id == user_id,
                InventoryTransaction.product_id == product_id,
            )
            .order_by(InventoryTransaction.inventory_transaction_id.desc())
        )
        if for_update:
            query = query.with_for_update()
        latest = query.first()
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

        # Đơn giá trên dòng hàng của giao dịch gắn với từng lần biến động (1 query cho cả trang)
        tx_ids = {tx.transaction_id for tx in txs if tx.transaction_id}
        detail_prices: Dict[int, Any] = {}
        if tx_ids:
            for d in (
                self.db.query(TransactionDetail.transaction_id, TransactionDetail.unit_price)
                .filter(
                    TransactionDetail.transaction_id.in_(tx_ids),
                    TransactionDetail.product_id == product_id,
                )
                .all()
            ):
                detail_prices.setdefault(d.transaction_id, d.unit_price)

        items = []
        for tx in txs:
            note_display = tx.note or ""
            has_customer = bool(tx.transaction_id and tx.transactions and getattr(tx.transactions, "customer_id", None))
            raw_price = detail_prices.get(tx.transaction_id)
            unit_price = float(raw_price) if raw_price is not None else None
            # IMPORT = giá nhập, SALE = giá bán, RETURN = khách trả hàng; None = nhập/xuất thủ công, kiểm kê
            if unit_price is None:
                price_type = None
            elif tx.inventory_type == "IN":
                price_type = "RETURN" if has_customer else "IMPORT"
            elif tx.inventory_type == "OUT":
                price_type = "SALE"
            else:
                price_type = None
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
                "unit_price": unit_price,
                "price_type": price_type,
                "subtotal": round(unit_price * float(tx.quantity), 2) if unit_price is not None else None,
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
