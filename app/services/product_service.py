from sqlalchemy.orm import Session
from app.repositories import product_repository as repo


class ProductService:

    @staticmethod
    def get_product_by_id(product_id: int, user_id: int, db: Session):
        return repo.get_product_by_id(db, user_id, product_id)

    @staticmethod
    def get_all_products(user_id: int, db: Session):
        return repo.get_all_products(db, user_id)

    @staticmethod
    def search_products_by_name(name: str, user_id: int, db: Session):
        return repo.search_products_by_name(db, user_id, name)

    @staticmethod
    def create_product(data: dict, user_id: int, db: Session):
        product = repo.create_product(
            db=db,
            user_id=user_id,
            name=data["name"],
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