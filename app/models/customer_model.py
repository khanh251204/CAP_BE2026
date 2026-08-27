from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    func
)

from app.configs.database import Base
from sqlalchemy.orm import relationship


class Customer(Base):
    __tablename__ = "Customer"

    customer_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=False,
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

    note = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    transactions = relationship(
        "Transaction",
        back_populates="customer"
    )

    user = relationship(
        "User",
        back_populates="customer"
    )

    debt = relationship(
        "Debt",
        back_populates="customer"
    )
