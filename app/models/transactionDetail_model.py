from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric
)

from sqlalchemy.orm import relationship

from app.configs.database import Base


class TransactionDetail(Base):
    __tablename__ = "Transaction_Detail"

    item_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id"),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("Product.product_id"),
        nullable=True
    )

    item_name = Column(
        String(255),
        nullable=False
    )

    quantity = Column(
        Numeric(15, 2),
        nullable=False
    )

    unit_price = Column(
        Numeric(15, 2),
        nullable=False
    )

    subtotal = Column(
        Numeric(15, 2),
        nullable=False
    )

    transaction = relationship(
        "Transaction",
        back_populates="details"
    )

    product = relationship(
        "Product",
        lazy="joined"
    )