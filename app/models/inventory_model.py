from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Enum
from datetime import datetime
from app.configs.database import Base
from sqlalchemy.orm import relationship


class InventoryTransaction(Base):
    __tablename__ = "Inventory_Transaction"

    inventory_transaction_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("Product.product_id"),
        nullable=False
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id"),
        nullable=False
    )

    type = Column(
        Enum("IN", "OUT"),
        nullable=False
    )

    quantity = Column(
        Numeric(15, 2),
        nullable=False
    )

    unit = Column(
        String(50),
        nullable=True
    )

    quantity_before = Column(
        Numeric(15, 2),
        nullable=False,
        default=0
    )

    quantity_after = Column(
        Numeric(15, 2),
        nullable=False,
        default=0
    )

    note = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime, 
        default=datetime.now,
        nullable=True
    )
    user = relationship(
        "User",
        back_populates="inventory_transaction"
    )
    product = relationship(
        "Product",
        back_populates="inventory_transaction"
    )
    transactions = relationship(
        "Transaction",
        back_populates="inventory_transaction"
    )