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

    # province từ Frontend
    region = Column(
        String(100),
        nullable=True
    )

    province_code = Column(
        String(20),
        nullable=True
    )

    ward_code = Column(
        String(20),
        nullable=True
    )

    ward_name = Column(
        String(150),
        nullable=True
    )

    address_detail = Column(
        String(255),
        nullable=True
    )

    # lĩnh vực kinh doanh
    business_type = Column(
        String(100),
        nullable=True
    )

    # personal | business
    account_type = Column(
        String(20),
        nullable=False,
        default="personal"
    )

    # Chỉ dành cho business
    store_name = Column(
        String(255),
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

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )