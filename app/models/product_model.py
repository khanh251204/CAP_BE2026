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

    image = Column(
        String(500),
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