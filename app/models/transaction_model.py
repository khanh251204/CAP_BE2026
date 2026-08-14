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
        ForeignKey("User.user_id"),
        nullable=False
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

    intent = Column(
        String(255),
        nullable=True
    )

    category_id = Column(
        Integer,
        ForeignKey("Category.category_id"),
        nullable=True
    )

    total_amount = Column(
        Numeric(15, 2),
        nullable=False
    )

    type = Column(
        Enum(
            "Income",
            "Expense",
            "Transfer",
            "Refund"
        ),
        nullable=False
    )

    payment_status = Column(
        String(50),
        nullable=True
    )

    input_method = Column(
        Enum(
             "Voice",
             "Manual"
        ),
        nullable=False
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
        nullable=False
    )

    updated_at = Column(
        DateTime,
        nullable=False
    )