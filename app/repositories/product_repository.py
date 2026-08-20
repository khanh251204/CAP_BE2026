from sqlalchemy.orm import Session

from app.models.product_model import Product


def get_product_by_name(
    db: Session,
    user_id: int,
    name: str
):

    return (
        db.query(Product)
        .filter(
            Product.user_id == 150002,
            Product.name == name
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
        user_id=150002,
        name=name,
        default_unit=unit,
        unit_price=price
    )

    db.add(product)

    db.flush()

    return product