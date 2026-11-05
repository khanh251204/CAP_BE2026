from typing import Optional, List, Any, Union, Dict
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.services.product_service import ProductService


class ProductController:

    # ==========================================
    # GET TẤT CẢ PRODUCT KÈM TỒN KHO - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def get_all_products_with_stock(user_id: int, db: Session):
        data = ProductService.get_all_products_with_stock(user_id, db)
        return {
            "success": True,
            "data": data
        }

    # ==========================================
    # GET CẢNH BÁO TỒN KHO (HẾT HÀNG / DƯỚI MIN_QUANTITY)
    # ==========================================
    @staticmethod
    def get_stock_alerts(user_id: int, db: Session, alert_type: Optional[str] = "ALL"):
        return ProductService.get_stock_alerts(user_id=user_id, db=db, alert_type=alert_type)
    # ==========================================
    # TÌM KIẾM PRODUCT THEO TÊN - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def search_products_by_name(
        name: str,
        user_id: int,
        db: Session
    ):
        data = ProductService.search_products_by_name(name, user_id, db)

        return {
            "success": True,
            "data": data
        }

    # ==========================================
    # GET TẤT CẢ PRODUCT - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def get_all_products(
        user_id: int,
        db: Session
    ):
        data = ProductService.get_all_products(user_id, db)

        return {
            "success": True,
            "data": data
        }

    # ==========================================
    # GET PRODUCT THEO USER (Dùng chung logic get_all)
    # ==========================================
    @staticmethod
    def get_products_by_user_id(
        user_id: int,
        db: Session
    ):
        return ProductController.get_all_products(user_id, db)

    # ==========================================
    # GET PRODUCT THEO ID - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def get_product_by_id(
        product_id: int,
        user_id: int,
        db: Session
    ):
        data = ProductService.get_product_by_id(product_id, user_id, db)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product"
            )

        return {
            "success": True,
            "data": data
        }

    # ==========================================
    # THÊM PRODUCT - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def create_product(
        data: Any,
        user_id: int,
        db: Session
    ):
        payload_dict = data.model_dump(exclude_unset=False) if hasattr(data, "model_dump") else (data.dict() if hasattr(data, "dict") else dict(data))
        product = ProductService.create_product(payload_dict, user_id, db)

        return {
            "success": True,
            "message": "Tạo Product thành công",
            "data": product
        }

    # ==========================================
    # SỬA PRODUCT - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def update_product(
        product_id: int,
        data: Any,
        user_id: int,
        db: Session
    ):
        payload_dict = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else (data.dict(exclude_unset=True) if hasattr(data, "dict") else dict(data))
        product = ProductService.update_product(product_id, payload_dict, user_id, db)

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product hoặc bạn không có quyền chỉnh sửa"
            )

        return {
            "success": True,
            "message": "Cập nhật Product thành công",
            "data": product
        }

    # ==========================================
    # XÓA PRODUCT - THEO USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def delete_product(
        product_id: int,
        user_id: int,
        db: Session
    ):
        result = ProductService.delete_product(product_id, user_id, db)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product hoặc bạn không có quyền xóa"
            )

        return result

    # ==========================================
    # KIỂM KÊ TỒN KHO (INVENTORY CHECK / ADJUSTMENT)
    # ==========================================
    @staticmethod
    def inventory_check(
        product_id: int,
        data: Any,
        user_id: int,
        db: Session
    ):
        payload_dict = data.model_dump() if hasattr(data, "model_dump") else (data.dict() if hasattr(data, "dict") else dict(data))
        actual_quantity = payload_dict.get("actual_quantity")
        if actual_quantity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thiếu thông tin actual_quantity"
            )

        try:
            actual_quantity_val = float(actual_quantity)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="actual_quantity phải là số"
            )

        note = payload_dict.get("note")
        raw_reason = payload_dict.get("reason")
        reason = getattr(raw_reason, "value", str(raw_reason)) if raw_reason else "ADJUSTMENT"

        return ProductService.inventory_check(
            product_id=product_id,
            actual_quantity=actual_quantity_val,
            note=note,
            reason=reason,
            count_unit=payload_dict.get("count_unit"),
            user_id=user_id,
            db=db
        )

    # ==========================================
    # NHẬP KHO / XUẤT KHO THỦ CÔNG
    # ==========================================
    @staticmethod
    def manual_inventory_transaction(
        product_id: int,
        data: Any,
        user_id: int,
        db: Session
    ):
        payload_dict = data.model_dump() if hasattr(data, "model_dump") else (data.dict() if hasattr(data, "dict") else dict(data))
        raw_inv_type = payload_dict.get("inventory_type")
        inventory_type = getattr(raw_inv_type, "value", str(raw_inv_type)) if raw_inv_type else None
        if not inventory_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thiếu thông tin inventory_type (IN hoặc OUT)"
            )

        quantity = payload_dict.get("quantity")
        if quantity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thiếu thông tin quantity"
            )

        try:
            quantity_val = float(quantity)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="quantity phải là số"
            )

        note = payload_dict.get("note")

        return ProductService.manual_inventory_transaction(
            product_id=product_id,
            inventory_type=inventory_type,
            quantity=quantity_val,
            note=note,
            user_id=user_id,
            db=db
        )

    # ==========================================
    # LỊCH SỬ TỒN KHO (INVENTORY HISTORY)
    # ==========================================
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
        return ProductService.get_inventory_history(
            product_id=product_id,
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            types=types,
            page=page,
            limit=limit,
            db=db
        )