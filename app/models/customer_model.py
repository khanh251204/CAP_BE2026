from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    func
)

from app.configs.database import Base


class Customer(Base):
    __tablename__ = "Customer"

    customer_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        Integer,
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
        nullable=True,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now()
    )