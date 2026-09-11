import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.product_model import Product
from app.repositories import product_repository as repo
from app.repositories.inventory_repo import InventoryRepository

logger = logging.getLogger(__name__)


class ProductService:

    @staticmethod
    def get_all_products_with_stock(user_id: int, db: Session):
        return repo.get_products_with_stock(db, user_id)

    @staticmethod
    def get_product_by_id(product_id: int, user_id: int, db: Session):
        return repo.get_product_by_id(db, user_id, product_id)

    @staticmethod
    def get_all_products(user_id: int, db: Session):
        return repo.get_all_products(db, user_id)

    @staticmethod
    def get_product_by_name(
        db: Session,
        user_id: int,
        name: str
    ):
        return (
            db.query(Product)
            .filter(
                Product.user_id == user_id,
                func.lower(Product.product_name) == name.strip().lower(),
                Product.is_active == True
            )
            .first()
        )

    @staticmethod
    def search_products_by_name(name: str, user_id: int, db: Session):
        return repo.search_products_by_name(db, user_id, name)

    @staticmethod
    def create_product(data: dict, user_id: int, db: Session):
        product_name = (data.get("product_name") or data.get("product") or "").strip()
        if not product_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên sản phẩm không được để trống"
            )

        if len(product_name) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên sản phẩm tối đa 255 ký tự"
            )

        # Kiểm tra trùng tên theo user_id
        existing_product = repo.get_product_by_name(
            db=db,
            user_id=user_id,
            product_name=product_name
        )

        if existing_product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sản phẩm '{product_name}' đã tồn tại"
            )

        default_unit = (data.get("default_unit") or data.get("unit") or "").strip()
        if not default_unit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đơn vị tính mặc định (default_unit) là bắt buộc"
            )

        try:
            unit_price = float(data.get("unit_price") or data.get("price") or 0.0)
            if unit_price <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unit_price phải là số lớn hơn 0"
            )

        try:
            min_quantity = float(data.get("min_quantity") or 0.0)
            if min_quantity < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_quantity phải là số lớn hơn hoặc bằng 0"
            )

        product = repo.create_product(
            db=db,
            user_id=user_id,
            product_name=product_name,
            unit=default_unit,
            price=unit_price
        )
        product.min_quantity = min_quantity
        if "img" in data:
            product.img = data["img"]

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def update_product(product_id: int, data: dict, user_id: int, db: Session):
        # Kiểm tra các field cấm sửa
        forbidden_fields = ["current_stock", "stock_quantity", "product_id", "user_id", "created_at"]
        for f in forbidden_fields:
            if f in data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Không được phép chỉnh sửa trường '{f}' qua API này"
                )

        product = repo.get_product_by_id(db, user_id, product_id)
        if not product:
            return None

        # Validation unit_price
        if "unit_price" in data and data["unit_price"] is not None:
            try:
                price_val = float(data["unit_price"])
                if price_val <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="unit_price phải lớn hơn 0"
                )

        # Validation min_quantity
        if "min_quantity" in data and data["min_quantity"] is not None:
            try:
                min_val = float(data["min_quantity"])
                if min_val < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="min_quantity phải lớn hơn hoặc bằng 0"
                )

        # Cảnh báo nếu đổi default_unit mà tồn kho > 0
        if "default_unit" in data and data["default_unit"] is not None:
            new_unit = str(data["default_unit"]).strip()
            if new_unit and new_unit != product.default_unit:
                inv_repo = InventoryRepository(db)
                current_stock = inv_repo.get_latest_stock(user_id=user_id, product_id=product_id)
                if current_stock > 0:
                    logger.warning(
                        f"[CẢNH BÁO] Đổi default_unit từ '{product.default_unit}' sang '{new_unit}' "
                        f"cho sản phẩm #{product_id} khi còn tồn kho {current_stock}"
                    )

        return repo.update_product(db, product, data)

    @staticmethod
    def delete_product(product_id: int, user_id: int, db: Session):
        product = repo.get_product_by_id(db, user_id, product_id)
        if not product:
            return None

        inv_repo = InventoryRepository(db)
        current_stock = inv_repo.get_latest_stock(user_id=user_id, product_id=product_id)

        # 1. Điều kiện: current_stock != 0 -> Từ chối xóa
        if current_stock != Decimal("0.0"):
            unit_display = product.default_unit or "đơn vị"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể xóa sản phẩm còn tồn kho ({current_stock} {unit_display}). Vui lòng xuất hết hàng hoặc điều chỉnh về 0 trước khi xóa."
            )

        # 2. Điều kiện: Đã từng phát sinh giao dịch -> Soft delete
        if inv_repo.has_any_history(product_id=product_id):
            repo.soft_delete_product(db, product)
            return {
                "success": True,
                "message": "Đã ẩn sản phẩm (giữ lịch sử giao dịch)",
                "mode": "soft_delete"
            }

        # 3. Điều kiện: Chưa từng có giao dịch -> Hard delete
        repo.hard_delete_product(db, product)
        return {
            "success": True,
            "message": "Đã xóa sản phẩm",
            "mode": "hard_delete"
        }

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

        # Tính trạng thái hiển thị
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