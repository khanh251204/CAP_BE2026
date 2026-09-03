from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.product_model import Product
from app.repositories import product_repository as repo


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

    from sqlalchemy import func

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
                func.lower(Product.name) == name.strip().lower(),
                Product.is_active == True
            )
            .first()
        )

    @staticmethod
    def search_products_by_name(name: str, user_id: int, db: Session):
        return repo.search_products_by_name(db, user_id, name)

    @staticmethod
    def create_product(data: dict, user_id: int, db: Session):

        name = data["name"].strip()

        # Kiểm tra trùng tên
        existing_product = repo.get_product_by_name(
            db=db,
            user_id=user_id,
            name=name
        )

        if existing_product:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Sản phẩm '{name}' đã tồn tại"
            )

        product = repo.create_product(
            db=db,
            user_id=user_id,
            name=name,
            unit=data.get("default_unit"),
            price=data.get("unit_price", 0.0)
        )

        db.commit()
        db.refresh(product)

        return product

    @staticmethod
    def update_product(product_id: int, data: dict, user_id: int, db: Session):
        product = repo.get_product_by_id(db, user_id, product_id)
        if not product:
            return None
        return repo.update_product(db, product, data)

    @staticmethod
    def delete_product(product_id: int, user_id: int, db: Session):
        product = repo.get_product_by_id(db, user_id, product_id)
        if not product:
            return None
        return repo.delete_product(db, product)