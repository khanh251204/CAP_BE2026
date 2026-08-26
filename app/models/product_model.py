from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    Boolean,
    DateTime
)

from app.configs.database import Base
from sqlalchemy.orm import relationship


class Product(Base):
    __tablename__ = "Product"

    product_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=False
    )

    img = Column(
        String(600),
        nullable=False
    )

    name = Column(
        String(255),
        nullable=False
    )

    default_unit = Column(
        String(50),
        nullable=True
    )
    unit_price = Column(
        Numeric(15, 2),
        nullable=True
    )

    min_quantity = Column(
        Numeric(15, 2),
        nullable=True
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at = Column(
        DateTime,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        nullable=False
    )

    transaction_details = relationship(
        "TransactionDetail",
        back_populates="product"
    )
    user = relationship(
        "User",
        back_populates="product"
    )
    inventory_transaction = relationship(
        "InventoryTransaction",
        back_populates="product"
    )