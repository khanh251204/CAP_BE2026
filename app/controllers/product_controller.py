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
        data: dict,
        user_id: int,
        db: Session
    ):
        product = ProductService.create_product(data, user_id, db)

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
        data: dict,
        user_id: int,
        db: Session
    ):
        product = ProductService.update_product(product_id, data, user_id, db)

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
    # XÓA PRODUCT - USER ĐĂNG NHẬP
    # ==========================================
    @staticmethod
    def delete_product(
        product_id: int,
        user_id: int,
        db: Session
    ):
        product = ProductService.delete_product(product_id, user_id, db)

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Product hoặc bạn không có quyền xóa"
            )

        return {
            "success": True,
            "message": "Xóa Product thành công"
        }