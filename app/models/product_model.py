from enum import Enum as PyEnum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    Numeric,
    Boolean,
    DateTime,
    Enum
)

from app.configs.database import Base
from sqlalchemy.orm import relationship


class ProductType(str, PyEnum):
    RESALE = "RESALE"
    RAW_MATERIAL = "RAW_MATERIAL"
    FINISHED_GOOD = "FINISHED_GOOD"


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
        Text,
        nullable=True
    )

    product_name = Column(
        String(255),
        nullable=False
    )

    default_unit = Column(
        String(50),
        nullable=True
    )

    unit_price = Column(
        Text,
        nullable=True
    )

    min_quantity = Column(
        Numeric(15, 2),
        nullable=True
    )

    product_type = Column(
        Enum("RESALE", "RAW_MATERIAL", "FINISHED_GOOD", name="product_type_enum"),
        nullable=True,
        default="RESALE"
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