from sqlalchemy.orm import Session
from app.services.product_service import ProductService


class ProductController:

    @staticmethod
    def get_product_by_id(
        product_id: int,
        db: Session
    ):
        data = ProductService.get_product_by_id(
            product_id,
            db
        )

        if not data:
            return {
                "success": False,
                "message": "KhÃ´ng tÃ¬m tháº¥y Product"
            }

        return {
            "success": True,
            "data": data
        }

    @staticmethod
    def get_all_products(db: Session):

        data = ProductService.get_all_products(db)

        return {
            "success": True,
            "data": data
        }

    @staticmethod
    def get_products_by_user_id(
        user_id: int,
        db: Session
    ):

        data = ProductService.get_products_by_user_id(
            user_id,
            db
        )

        return {
            "success": True,
            "data": data
        }

    @staticmethod
    def create_product(
        data: dict,
        db: Session
    ):

        product = ProductService.create_product(
            data,
            db
        )

        return {
            "success": True,
            "message": "Táº¡o Product thÃ nh cÃ´ng",
            "data": product
        }

    @staticmethod
    def update_product(
        product_id: int,
        data: dict,
        db: Session
    ):

        product = ProductService.update_product(
            product_id,
            data,
            db
        )

        if not product:
            return {
                "success": False,
                "message": "KhÃ´ng tÃ¬m tháº¥y Product"
            }

        return {
            "success": True,
            "message": "Cáº­p nháº­t Product thÃ nh cÃ´ng",
            "data": product
        }

    @staticmethod
    def delete_product(
        product_id: int,
        db: Session
    ):

        product = ProductService.delete_product(
            product_id,
            db
        )

        if not product:
            return {
                "success": False,
                "message": "KhÃ´ng tÃ¬m tháº¥y Product"
            }

        return {
            "success": True,
            "message": "XÃ³a Product thÃ nh cÃ´ng"
        }
