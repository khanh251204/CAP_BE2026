from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import app.repositories.product_repository as repo
from app.repositories.inventory_repo import InventoryRepository


class ProductInventoryService:

    @staticmethod
    def inventory_check(
        product_id: int,
        actual_quantity: float,
        note: Optional[str],
        reason: str,
        user_id: int,
        db: Session
    ):
        """
        API Kiểm kê tồn kho:
        1. Lock row Product.
        2. quantity_before = current_stock.
        3. quantity_after = actual_quantity.
        4. delta = quantity_after - quantity_before.
        5. Tạo Inventory_Transaction loại reason (mặc định ADJUSTMENT).
        6. Tính trạng thái hiển thị 'Còn hàng' / 'Hết hàng'.
        """
        product = repo.get_product_with_lock(db, user_id, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product hoặc bạn không có quyền thao tác"
            )

        if actual_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="actual_quantity không được nhỏ hơn 0"
            )

        inv_repo = InventoryRepository(db)
        qty_before = inv_repo.get_latest_stock(user_id, product_id)
        qty_after = Decimal(str(actual_quantity))
        delta = qty_after - qty_before

        inv_type = reason.upper() if reason else "ADJUSTMENT"
        if inv_type not in ["ADJUSTMENT", "DAMAGE"]:
            inv_type = "ADJUSTMENT"

        inv_tx = inv_repo.create_inventory_transaction(
            user_id=user_id,
            product_id=product_id,
            transaction_id=None,
            type=inv_type,
            quantity=abs(delta),
            unit=product.default_unit or "",
            quantity_before=qty_before,
            quantity_after=qty_after,
            note=note or "Kiểm kho định kỳ",
        )

        db.commit()
        db.refresh(inv_tx)

        min_qty = Decimal(str(product.min_quantity)) if product.min_quantity is not None else Decimal("0.0")
        status_display = "Còn hàng" if qty_after > min_qty and qty_after > Decimal("0.0") else "Hết hàng"

        return {
            "product_id": product.product_id,
            "quantity_before": float(qty_before),
            "quantity_after": float(qty_after),
            "delta": float(delta),
            "status": status_display
        }

    @staticmethod
    def manual_inventory_transaction(
        product_id: int,
        inventory_type: str,
        quantity: float,
        note: Optional[str],
        user_id: int,
        db: Session
    ):
        """
        API phụ: Nhập kho / Xuất kho thủ công:
        - inventory_type: IN | OUT
        - quantity > 0
        - Nếu OUT mà quantity > current_stock -> 409 Conflict
        """
        product = repo.get_product_with_lock(db, user_id, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product hoặc bạn không có quyền thao tác"
            )

        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="quantity phải lớn hơn 0"
            )

        inv_type = inventory_type.upper()
        if inv_type not in ["IN", "OUT"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="inventory_type phải là 'IN' hoặc 'OUT'"
            )

        inv_repo = InventoryRepository(db)
        qty_before = inv_repo.get_latest_stock(user_id, product_id)
        qty_change = Decimal(str(quantity))

        if inv_type == "OUT":
            if qty_change > qty_before:
                unit_str = product.default_unit or "đơn vị"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Số lượng xuất vượt quá tồn kho hiện có (còn {qty_before} {unit_str})"
                )
            qty_after = qty_before - qty_change
        else:
            qty_after = qty_before + qty_change

        inv_tx = inv_repo.create_inventory_transaction(
            user_id=user_id,
            product_id=product_id,
            transaction_id=None,
            type=inv_type,
            quantity=qty_change,
            unit=product.default_unit or "",
            quantity_before=qty_before,
            quantity_after=qty_after,
            note=note or f"{'Nhập' if inv_type == 'IN' else 'Xuất'} kho thủ công",
        )

        db.commit()
        db.refresh(inv_tx)

        return {
            "product_id": product.product_id,
            "inventory_transaction_id": inv_tx.inventory_transaction_id,
            "inventory_type": inv_tx.inventory_type,
            "quantity": float(inv_tx.quantity),
            "quantity_before": float(qty_before),
            "quantity_after": float(qty_after),
            "note": inv_tx.note,
            "created_at": inv_tx.created_at.isoformat() if inv_tx.created_at else None
        }

    @staticmethod
    def get_inventory_history(
        product_id: int,
        user_id: int,
        from_date: Optional[datetime],
        to_date: Optional[datetime],
        types: Optional[List[str]],
        page: int,
        limit: int,
        db: Session
    ):
        product = repo.get_product_by_id(db, user_id, product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product hoặc bạn không có quyền truy cập"
            )

        inv_repo = InventoryRepository(db)
        history = inv_repo.get_inventory_history(
            user_id=user_id,
            product_id=product_id,
            from_date=from_date,
            to_date=to_date,
            types=types,
            page=page,
            limit=limit
        )

        return {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "total": history["total"],
            "items": history["items"]
        }
