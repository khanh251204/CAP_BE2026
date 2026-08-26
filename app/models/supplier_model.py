from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    func
)

from sqlalchemy.orm import relationship

from app.configs.database import Base


class Supplier(Base):
    __tablename__ = "Supplier"

    supplier_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=True,
        index=True
    )

    name = Column(
        String(255),
        nullable=False
    )

    phone_number = Column(
        String(20),
        nullable=True
    )

    email = Column(
        String(255),
        nullable=True
    )

    address = Column(
        String(255),
        nullable=True
    )

    product_group = Column(
        String(100),
        nullable=True
    )

    tax_code = Column(
        String(50),
        nullable=True
    )

    note = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=True,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now()
    )

    transactions = relationship(
        "Transaction",
        back_populates="supplier"
    )

    user = relationship(
        "User",
        back_populates="supplier"
    )

    debt = relationship(
        "Debt",
        back_populates="supplier"
    )