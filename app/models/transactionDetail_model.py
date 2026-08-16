from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
)
from sqlalchemy.orm import relationship

from app.configs.database import Base
class TransactionDetail(Base):
    __tablename__ = "Transaction_Detail"

    detail_id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("Transaction.transaction_id"), nullable=True)
    product_id = Column(Integer, ForeignKey("Product.product_id"), nullable=True)
    quantity = Column(Numeric(15, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=True)
    subtotal = Column(Numeric(15, 2), nullable=False)
    transaction = relationship(
            "Transaction",
            back_populates="transaction_detail"
        )
    product = relationship(
            "Product",
            back_populates="transaction_details"
        )