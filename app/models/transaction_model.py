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
from sqlalchemy.orm import relationship, synonym
from datetime import datetime

from app.configs.database import Base


class Transaction(Base):
    __tablename__ = "Transaction"

    transaction_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=False
    )

    intent_id = Column(
        Integer,
        ForeignKey("Intent.intent_id"),
        nullable=True
    )

    category_id = Column(
        Integer,
        ForeignKey("Category.category_id"),
        nullable=True
    )

    account_id = Column(
        Integer,
        ForeignKey("Account.account_id"),
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

    # CẢNH BÁO: Trường 'type' không có trong đặc tả ERD gốc.
    # Được giữ nguyên theo quy tắc để tránh phá vỡ logic code hiện hữu.
    # type = Column(
    #     Enum("INCOME", "EXPENSE", "TRANSFER", "REFUND", name="transaction_type_enum"),
    #     nullable=True
    # )

    total_amount = Column(
        Numeric(15, 2),
        nullable=False,
        default=0
    )

    # Giới hạn đúng 3 giá trị theo ERD: 'PAID', 'PARTIAL', 'PENDING'
    payment_status = Column(
        Enum("PAID", "PARTIAL", "PENDING", name="payment_status_enum"),
        nullable=False,
        default="PENDING"
    )

    # Giới hạn đúng 2 giá trị theo ERD: 'VOICE', 'MANUAL'
    input_method = Column(
        Enum("VOICE", "MANUAL", name="input_method_enum"),
        nullable=False,
        default="MANUAL"
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
        nullable=False,
        default=datetime.now
    )

    created_at = Column(
        DateTime, 
        default=datetime.now,
        nullable=True
    )

    updated_at = Column(
        DateTime, 
        default=datetime.now, 
        onupdate=datetime.now,
        nullable=True
    )

    # Relationships (1-N hoặc N-1 theo ERD)
    user = relationship(
        "User",
        back_populates="transactions"
    )
    intent = relationship(
        "Intent",
        back_populates="transactions"
    )
    category = relationship(
        "Category",
        back_populates="transactions"
    )
    account = relationship(
        "Account",
        back_populates="transactions"
    )
    customer = relationship(
        "Customer",
        back_populates="transactions"
    )
    supplier = relationship(
        "Supplier",
        back_populates="transactions"
    )
    transaction_detail = relationship(
        "TransactionDetail",
        back_populates="transaction"
    )
    inventory_transaction = relationship(
        "InventoryTransaction",
        back_populates="transactions"
    )
    debt = relationship(
        "Debt",
        back_populates="transaction"
    )
    debt_payments = relationship(
        "DebtPayment",
        back_populates="transaction"
    )
    voice_records = relationship(
        "VoiceRecord",
        back_populates="transaction"
    )