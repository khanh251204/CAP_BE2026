from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    String
)
from sqlalchemy.orm import relationship, synonym
from datetime import datetime

from app.configs.database import Base


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

    # # CẢNH BÁO: 'counterparty_name' không có trong ERD gốc.
    # # Được giữ nguyên theo quy tắc để đảm bảo tương thích ngược.
    # counterparty_name = Column(
    #     String(255),
    #     nullable=True
    # )

    # Giới hạn đúng 2 giá trị theo ERD: 'RECEIVABLE', 'PAYABLE'
    direction = Column(
        Enum("RECEIVABLE", "PAYABLE", name="debt_direction_enum"),
        nullable=False
    )

    original_amount = Column(
        Numeric(15, 2),
        nullable=False,
        default=0
    )

    # Đổi tên theo ERD chuẩn: remaining_debt
    remaining_debt = Column(
        Numeric(15, 2),
        nullable=False,
        default=0
    )

    # Giới hạn đúng 3 giá trị theo ERD: 'UNPAID', 'PARTIAL', 'PAID'
    status = Column(
        Enum("UNPAID", "PARTIAL", "PAID", name="debt_status_enum"),
        nullable=False,
        default="UNPAID"
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

    # Backward compatibility synonyms
    source_transaction_id = synonym("transaction_id")
    remaining_amount = synonym("remaining_debt")
    total_debt = synonym("original_amount")

    # Relationships (theo bảng Mối quan hệ trong ERD)
    user = relationship(
        "User",
        back_populates="debt"
    )
    transaction = relationship(
        "Transaction",
        back_populates="debt"
    )
    source_transaction = synonym("transaction")

    customer = relationship(
        "Customer",
        back_populates="debt"
    )
    supplier = relationship(
        "Supplier",
        back_populates="debt"
    )
    payments = relationship(
        "DebtPayment",
        back_populates="debt"
    )