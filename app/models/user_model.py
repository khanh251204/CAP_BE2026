from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    text
)

from app.configs.database import Base


class User(Base):
    __tablename__ = "User"

    user_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    full_name = Column(
        String(255),
        nullable=False
    )

    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    phone_number = Column(
        String(20),
        nullable=True
    )

    password_hash = Column(
        String(255),
        nullable=True
    )

    # API province -> DB region
    region = Column(
        String(100),
        nullable=True
    )

    # API businessField -> DB business_type
    business_type = Column(
        String(100),
        nullable=True
    )

    google_id = Column(
        String(255),
        nullable=True
    )

    apple_id = Column(
        String(255),
        nullable=True
    )

    is_verified = Column(
        Boolean,
        nullable=False,
        default=False
    )

    role = Column(
        String(30),
        nullable=False,
        default="user"
    )

    account_type = Column(
        String(20),
        nullable=False,
        default="personal"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )