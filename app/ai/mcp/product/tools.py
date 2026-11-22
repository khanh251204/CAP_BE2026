from typing import Optional, Any

from fastapi import HTTPException

from app.services.product_service import ProductService
from app.configs.database import SessionLocal


class ProductTools:

    @staticmethod
    def _product_to_dict(product):
        if not product:
            return None

        return {
            "product_id": product.product_id,
            "name": product.product_name,
            "default_unit": product.default_unit,
            "unit_price": product.unit_price
        }

    @staticmethod
    def get_all_products(
        user_id: int
    ):
        db = SessionLocal()

        try:
            products = ProductService.get_all_products(
                user_id=user_id,
                db=db
            )

            return {
                "success": True,
                "products": [
                    ProductTools._product_to_dict(product)
                    for product in products
                ]
            }

        finally:
            db.close()

    @staticmethod
    def get_product_by_id(
        product_id: int,
        user_id: int
    ):
        db = SessionLocal()

        try:
            product = ProductService.get_product_by_id(
                product_id=product_id,
                user_id=user_id,
                db=db
            )

            if not product:
                return {
                    "success": False,
                    "message": "Không tìm thấy sản phẩm"
                }

            return {
                "success": True,
                "product": ProductTools._product_to_dict(product)
            }

        finally:
            db.close()

    @staticmethod
    def search_products(
        name: str,
        user_id: int
    ):
        db = SessionLocal()

        try:
            products = ProductService.search_products_by_name(
                name=name,
                user_id=user_id,
                db=db
            )

            return {
                "success": True,
                "products": [
                    {
                        "product_id": product.product_id,
                        "product_name": product.product_name,
                        "default_unit": product.default_unit,
                        "unit_price": product.unit_price
                    }
                    for product in products
                ]
            }

        finally:
            db.close()

    @staticmethod
    def find_duplicate_product(
        name: str,
        user_id: int
    ):
        """
        MCP tool: kiểm tra đã có sản phẩm TRÙNG TÊN chưa (khớp chính xác sau khi chuẩn hóa
        hoa/thường, khoảng trắng). Khác search_products (tìm chứa chuỗi): có "Coca" vẫn thêm được "Coca Zero".
        """
        from app.services.duplicate_guard import find_duplicate_product

        db = SessionLocal()
        try:
            product = find_duplicate_product(db, user_id, name)
            return {
                "success": True,
                "exists": product is not None,
                "product": {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "default_unit": product.default_unit,
                    "unit_price": product.unit_price,
                } if product else None,
            }
        finally:
            db.close()

    @staticmethod
    def get_products_with_stock(
        user_id: int
    ):
        db = SessionLocal()

        try:
            products = ProductService.get_all_products_with_stock(
                user_id=user_id,
                db=db
            )

            return {
                "success": True,
                "products": [
                    ProductTools._product_to_dict(product)
                    for product in products
                ]
            }

        finally:
            db.close()

    @staticmethod
    def create_product(
        name: str,
        default_unit: Optional[str],
        unit_price: float,
        user_id: int
    ):
        db = SessionLocal()

        try:
            data = {
                "product_name": name,
                "default_unit": default_unit.strip() if default_unit else "cái",
                "unit_price": unit_price,
            }

            product = ProductService.create_product(
                data=data,
                user_id=user_id,
                db=db
            )

            return {
                "success": True,
                "message": "Tạo sản phẩm thành công",
                "product": ProductTools._product_to_dict(product)
            }

        except Exception as e:
            db.rollback()

            return {
                "success": False,
                "message": "Không thể tạo sản phẩm",
                "error": str(e)
            }

        finally:
            db.close()

    @staticmethod
    def update_product(
        product_id: int,
        data: dict[str, Any],
        user_id: int
    ):
        db = SessionLocal()

        try:
            product = ProductService.update_product(
                product_id=product_id,
                data=data,
                user_id=user_id,
                db=db
            )

            if not product:
                return {
                    "success": False,
                    "message": "Không tìm thấy sản phẩm"
                }

            return {
                "success": True,
                "message": "Cập nhật sản phẩm thành công",
                "product": ProductTools._product_to_dict(product)
            }

        except HTTPException as e:
            # Lỗi kiểm tra (trùng tên, đổi đơn vị khi đang có định mức...) -> trả lời được cho người dùng
            return {"success": False, "message": str(e.detail)}

        finally:
            db.close()

    @staticmethod
    def delete_product(
        product_id: int,
        user_id: int
    ):
        db = SessionLocal()

        try:
            product = ProductService.delete_product(
                product_id=product_id,
                user_id=user_id,
                db=db
            )

            if not product:
                return {
                    "success": False,
                    "message": "Không tìm thấy sản phẩm"
                }

            return {
                "success": True,
                "message": "Xóa sản phẩm thành công"
            }

        finally:
            db.close()