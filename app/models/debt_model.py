from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum
)
from datetime import datetime

from app.configs.database import Base
from sqlalchemy.orm import relationship



class Debt(Base):
    __tablename__ = "Debt"

    debt_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id"),
        nullable=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=False
    )

    customer_id = Column(
        Integer,
        ForeignKey("Customer.customer_id"),
        nullable=True
    )

    supplier_id = Column(
        Integer,
        ForeignKey("Supplier.supplier_id"),
        nullable=True
    )

    direction = Column(
        Enum("RECEIVABLE", "PAYABLE"),
        nullable=False
    )

    total_debt = Column(
        Numeric(15, 2),
        nullable=False,
        default=0
    )


    status = Column(
        Enum("Đã thanh toán", "Chưa thanh toán", "Chờ xác nhận", "Thanh toán một phần"),
        nullable=False,
        default="Đã thanh toán"
    )

    created_at = Column(
            DateTime, 
            default=datetime.now,
            nullable=True
        )
    
    updated_at = Column(
            DateTime, 
            default=datetime.now, 
            onupdate=datetime.now, # Tự động cập nhật lại giờ khi có chỉnh sửa
            nullable=True
        )
    user = relationship(
        "User",
        back_populates="debt"
     )
    transactions = relationship(
        "Transaction",
        back_populates="debt"
     )
    customer = relationship(
        "Customer",
        back_populates="debt"
     )
    supplier = relationship(
        "Supplier",
        back_populates="debt"
     )