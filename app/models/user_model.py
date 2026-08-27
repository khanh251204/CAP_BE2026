from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    text
)

from sqlalchemy.orm import relationship

from app.configs.database import Base


class User(Base):
    __tablename__ = "User"

    # PRIMARY KEY
    user_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # BASIC INFORMATION
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

    # LOCATION
    # Tỉnh / thành phố từ Frontend
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

    # BUSINESS INFORMATION
    # Lĩnh vực kinh doanh
    business_type = Column(
        String(100),
        nullable=True
    )

    account_type = Column(
        String(20),
        nullable=False,
        default="business"
    )

    # STORE INFORMATION
    store_name = Column(
        String(255),
        nullable=True
    )

    # SOCIAL LOGIN
    google_id = Column(
        String(255),
        nullable=True
    )

    apple_id = Column(
        String(255),
        nullable=True
    )

    # ACCOUNT STATUS
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False
    )

    # LOGIN LOCK SYSTEM
    failed_attempts = Column(
        Integer,
        nullable=False,
        default=0
    )

    lock_until = Column(
        DateTime,
        nullable=True
    )

    # ROLE
    role = Column(
        String(30),
        nullable=False,
        default="user"
    )

    # TIMESTAMP
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # RELATIONSHIPS
    transactions = relationship(
        "Transaction",
        back_populates="user"
    )

    customer = relationship(
        "Customer",
        back_populates="user"
    )

    supplier = relationship(
        "Supplier",
        back_populates="user"
    )

    account = relationship(
        "Account",
        back_populates="user"
    )

    product = relationship(
        "Product",
        back_populates="user"
    )

    inventory_transaction = relationship(
        "InventoryTransaction",
        back_populates="user"
    )

    debt = relationship(
        "Debt",
        back_populates="user"
    )