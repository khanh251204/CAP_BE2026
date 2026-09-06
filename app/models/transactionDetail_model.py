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
    
    # 1. Bắt buộc phải có transaction_id (nullable=False)
    transaction_id = Column(Integer, ForeignKey("Transaction.transaction_id"), nullable=False)
    
    # 2. Bắt buộc phải có product_id (nullable=False)
    product_id = Column(Integer, ForeignKey("Product.product_id"), nullable=False)
    
    quantity = Column(Numeric(15, 0), nullable=False)
    unit = Column(String(50), nullable=False)
    
    # 3. Đơn giá không được để NULL, mặc định = 0.00
    unit_price = Column(Numeric(15, 2), nullable=False, default=0.00)
    subtotal = Column(Numeric(15, 2), nullable=False, default=0.00)

    # Relationships
    transaction = relationship(
        "Transaction",
        back_populates="transaction_detail"  # Lưu ý kiểm tra bên Transaction model xem đặt tên là transaction_detail hay transaction_details
    )
    product = relationship(
        "Product",
        back_populates="transaction_details"
    )