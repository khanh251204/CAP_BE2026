from sqlalchemy.orm import Session
from app.models.product_model import Product


def get_product_by_name(db: Session, user_id: int, name: str):
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.name == name,
            Product.is_active == True
        )
        .first()
    )


def create_product(
    db: Session,
    user_id: int,
    name: str,
    unit: str | None,
    price: float
):
    product = Product(
        user_id=user_id,
        name=name,
        default_unit=unit,
        unit_price=price,
        is_active=True
    )
    db.add(product)
    db.flush()
    return product


def get_product_by_id(db: Session, user_id: int, product_id: int):
    return (
        db.query(Product)
        .filter(
            Product.product_id == product_id,
            Product.user_id == user_id,
            Product.is_active == True
        )
        .first()
    )


def get_all_products(db: Session, user_id: int):
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.is_active == True
        )
        .all()
    )


def search_products_by_name(db: Session, user_id: int, name: str):
    return (
        db.query(Product)
        .filter(
            Product.user_id == user_id,
            Product.is_active == True,
            Product.name.ilike(f"%{name}%")
        )
        .all()
    )


def update_product(db: Session, product: Product, data: dict):
    if "name" in data:
        product.name = data["name"]
    if "default_unit" in data:
        product.default_unit = data["default_unit"]
    if "min_quantity" in data:
        product.min_quantity = data["min_quantity"]
    if "unit_price" in data:
        product.unit_price = data["unit_price"]

    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product):
    product.is_active = False
    db.commit()
    db.refresh(product)
    return product