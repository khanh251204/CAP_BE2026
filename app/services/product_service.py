import logging
from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.product_model import Product
from app.repositories import product_repository as repo
from app.repositories.inventory_repo import InventoryRepository
from app.services.product_inventory_service import ProductInventoryService
from app.services.duplicate_guard import clean_name, ensure_unique_product

logger = logging.getLogger(__name__)


class ProductService:

    @staticmethod
    def get_all_products_with_stock(user_id: int, db: Session):
        return repo.get_products_with_stock(db, user_id)

    @staticmethod
    def get_stock_alerts(user_id: int, db: Session, alert_type: Optional[str] = "ALL"):
        from app.services.stock_alert_service import StockAlertService
        return StockAlertService.get_stock_alerts(db=db, user_id=user_id, alert_type=alert_type)

    @staticmethod
    def get_product_by_id(product_id: int, user_id: int, db: Session):
        return repo.get_product_by_id(db, user_id, product_id)

    @staticmethod
    def get_all_products(user_id: int, db: Session):
        return repo.get_all_products(db, user_id)

    @staticmethod
    def get_product_by_name(db: Session, user_id: int, name: str):
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
        product_name = clean_name(data.get("product_name") or data.get("product") or data.get("name") or "")
        if not product_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên sản phẩm không được để trống")
        if len(product_name) > 255:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên sản phẩm tối đa 255 ký tự")

        # Không cho trùng tên (không phân biệt hoa/thường, khoảng trắng thừa) với sản phẩm đang kinh doanh
        ensure_unique_product(db, user_id, product_name)

        default_unit = str(data.get("default_unit") or data.get("unit") or "").strip()
        if not default_unit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn vị tính mặc định (default_unit) là bắt buộc")
        if len(default_unit) > 50:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn vị tính tối đa 50 ký tự")

        try:
            raw_p = data.get("unit_price") if data.get("unit_price") is not None else data.get("price")
            if raw_p is None:
                raise ValueError()
            unit_price = float(raw_p)
            if unit_price <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unit_price phải là số lớn hơn 0")

        try:
            raw_q = data.get("min_quantity") if data.get("min_quantity") is not None else 0.0
            min_quantity = float(raw_q)
            if min_quantity < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_quantity phải là số lớn hơn hoặc bằng 0")

        product_type = data.get("product_type")
        if product_type is not None:
            pt_val = str(getattr(product_type, "value", product_type)).strip().upper()
            if pt_val not in ("RESALE", "RAW_MATERIAL", "FINISHED_GOOD"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="product_type chỉ chấp nhận một trong các giá trị: RESALE, RAW_MATERIAL, FINISHED_GOOD"
                )
            product_type = pt_val
        else:
            from app.models.user_model import User
            user_obj = db.query(User).filter(User.user_id == user_id).first()
            user_bt = str(getattr(user_obj, "business_type", "") or "").strip().upper()
            product_type = "FINISHED_GOOD" if user_bt == "PRODUCER" else "RESALE"

        product = repo.create_product(
            db=db, user_id=user_id, product_name=product_name, unit=default_unit, price=unit_price, product_type=product_type
        )
        product.min_quantity = min_quantity
        if "img" in data and data["img"]:
            product.img = data["img"]

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def update_product(product_id: int, data: dict, user_id: int, db: Session):
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

        if "product_name" in data:
            if data["product_name"] is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên sản phẩm không được để trống")
            new_name = clean_name(data["product_name"])
            if not new_name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên sản phẩm không được để trống")
            if len(new_name) > 255:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên sản phẩm tối đa 255 ký tự")
            # Đổi tên trùng với sản phẩm khác cũng bị chặn
            ensure_unique_product(db, user_id, new_name, exclude_id=product.product_id)
            data["product_name"] = new_name

        if "default_unit" in data:
            if data["default_unit"] is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn vị tính không được để trống")
            clean_unit = str(data["default_unit"]).strip()
            if not clean_unit:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn vị tính không được để trống")
            if len(clean_unit) > 50:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn vị tính tối đa 50 ký tự")
            data["default_unit"] = clean_unit

        if "product_type" in data and data["product_type"] is not None:
            pt_val = str(getattr(data["product_type"], "value", data["product_type"])).strip().upper()
            if pt_val not in ("RESALE", "RAW_MATERIAL", "FINISHED_GOOD"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="product_type chỉ chấp nhận một trong các giá trị: RESALE, RAW_MATERIAL, FINISHED_GOOD"
                )
            data["product_type"] = pt_val

        if "unit_price" in data and data["unit_price"] is not None:
            try:
                price_val = float(data["unit_price"])
                if price_val <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unit_price phải lớn hơn 0")

        if "min_quantity" in data and data["min_quantity"] is not None:
            try:
                min_val = float(data["min_quantity"])
                if min_val < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_quantity phải lớn hơn hoặc bằng 0")

        # Đơn vị quy đổi / định mức đang tính theo đơn vị & loại hiện tại -> chặn đổi làm sai số liệu
        from app.services.bom_service import product_change_conflict
        conflict = product_change_conflict(db, user_id, product, data)
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)

        if "default_unit" in data and data["default_unit"] is not None:
            new_unit = str(data["default_unit"]).strip()
            if new_unit and new_unit != product.default_unit:
                inv_repo = InventoryRepository(db)
                current_stock = inv_repo.get_latest_stock(user_id=user_id, product_id=product_id)
                if current_stock > 0:
                    logger.warning(
                        f"[CẢNH BÁO] Đổi default_unit từ '{product.default_unit}' sang '{new_unit}' cho #{product_id} khi còn tồn kho {current_stock}"
                    )

        return repo.update_product(db, product, data)

    @staticmethod
    def delete_product(product_id: int, user_id: int, db: Session):
        product = repo.get_product_by_id(db, user_id, product_id)
        if not product:
            return None

        inv_repo = InventoryRepository(db)
        current_stock = inv_repo.get_latest_stock(user_id=user_id, product_id=product_id)

        if current_stock != Decimal("0.0"):
            unit_display = product.default_unit or "đơn vị"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể xóa sản phẩm còn tồn kho ({current_stock} {unit_display}). Vui lòng xuất hết hàng hoặc điều chỉnh về 0 trước khi xóa."
            )

        if inv_repo.has_any_history(product_id=product_id):
            repo.soft_delete_product(db, product)
            return {"success": True, "message": "Đã ẩn sản phẩm (giữ lịch sử giao dịch)", "mode": "soft_delete"}

        repo.hard_delete_product(db, product)
        return {"success": True, "message": "Đã xóa sản phẩm", "mode": "hard_delete"}

    @staticmethod
    def inventory_check(product_id: int, actual_quantity: float, note: Optional[str], reason: str, user_id: int, db: Session,
                        count_unit: Optional[str] = None):
        return ProductInventoryService.inventory_check(
            product_id=product_id, actual_quantity=actual_quantity, note=note, reason=reason, user_id=user_id, db=db,
            count_unit=count_unit,
        )

    @staticmethod
    def manual_inventory_transaction(product_id: int, inventory_type: str, quantity: float, note: Optional[str], user_id: int, db: Session):
        return ProductInventoryService.manual_inventory_transaction(
            product_id=product_id, inventory_type=inventory_type, quantity=quantity, note=note, user_id=user_id, db=db
        )

    @staticmethod
    def get_inventory_history(product_id: int, user_id: int, from_date: Optional[datetime], to_date: Optional[datetime], types: Optional[List[str]], page: int, limit: int, db: Session):
        return ProductInventoryService.get_inventory_history(
            product_id=product_id, user_id=user_id, from_date=from_date, to_date=to_date, types=types, page=page, limit=limit, db=db
        )