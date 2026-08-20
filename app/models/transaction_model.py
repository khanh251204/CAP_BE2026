from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    Enum,
    Text,
    DateTime
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.configs.database import Base
class Transaction(Base):
    __tablename__ = "Transaction"

    transaction_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        # ForeignKey("User.user_id"),
        nullable=False
    )
    # category_id = Column(
    #         Integer,
    #         ForeignKey("Category.category_id"),
    #         nullable=True
    #     )

    account_id = Column(
        Integer,
        ForeignKey("Account.account_id"),
        nullable=True
    )
    intent_id = Column(
        Integer,
        ForeignKey("Intent.intent_id"),
        nullable=True
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
    total_amount = Column(
        Numeric(15, 2),
        nullable=False
    )


    payment_status = Column(
        String(50),
        nullable=True
    )

    input_method = Column(
        Enum(
             "VOICE",
             "MANUAL"
        ),
        nullable=False
    )
    input_text = Column(
        Text,
        nullable=True
    )

    note = Column(
        Text,
        nullable=True
    )

    transaction_date = Column(
        DateTime,
        nullable=False
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

    transaction_detail = relationship(
        "TransactionDetail",
        back_populates="transaction"
    )
    # category = relationship(
    #     "Category",
    #     back_populates="transactions"
    # )
    customer = relationship(
        "Customer",
        back_populates="transactions"
    )
    supplier = relationship(
        "Supplier",
        back_populates="transactions"
    )
    account = relationship(
        "Account",
        back_populates="transactions"
    )
    intent = relationship(
        "Intent",
        back_populates="transactions"
    )

   