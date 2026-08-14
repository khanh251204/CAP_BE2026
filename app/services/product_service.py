from sqlalchemy.orm import Session
from app.models.product import Product


class ProductService:

    # Lấy 1 product
    @staticmethod
    def get_product_by_id(product_id: int, db: Session):
        return db.query(Product).filter(
            Product.product_id == product_id
        ).first()

    # Lấy tất cả product
    @staticmethod
    def get_all_products(db: Session):
        return db.query(Product).filter(
            Product.is_active == True
        ).all()

    # Lấy product theo user
    @staticmethod
    def get_products_by_user_id(user_id: int, db: Session):
        return db.query(Product).filter(
            Product.user_id == user_id,
            Product.is_active == True
        ).all()

    # Xác nhận / nhập tay Product
    @staticmethod
    def create_product(data: dict, db: Session):

        product = Product(
            user_id=data["user_id"],
            name=data["name"],
            default_unit=data.get("default_unit"),
            min_quantity=data.get("min_quantity"),
            is_active=True
        )

        db.add(product)
        db.commit()
        db.refresh(product)

        return product

    # Sửa Product
    @staticmethod
    def update_product(
        product_id: int,
        data: dict,
        db: Session
    ):

        product = db.query(Product).filter(
            Product.product_id == product_id,
            Product.is_active == True
        ).first()

        if not product:
            return None

        if "name" in data:
            product.name = data["name"]

        if "default_unit" in data:
            product.default_unit = data["default_unit"]

        if "min_quantity" in data:
            product.min_quantity = data["min_quantity"]

        db.commit()
        db.refresh(product)

        return product

    # Xóa mềm
    @staticmethod
    def delete_product(
        product_id: int,
        db: Session
    ):

        product = db.query(Product).filter(
            Product.product_id == product_id,
            Product.is_active == True
        ).first()

        if not product:
            return None

        product.is_active = False

        db.commit()
        db.refresh(product)

        return product