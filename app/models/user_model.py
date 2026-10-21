from enum import Enum as PyEnum
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    text
)

from app.configs.database import Base
from sqlalchemy.orm import relationship


class BusinessType(str, PyEnum):
    RESELLER = "RESELLER"
    PRODUCER = "PRODUCER"
    SERVICE = "SERVICE"


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

    # Loại hình kinh doanh chuẩn: RESELLER (mua về bán lại) | PRODUCER (sản xuất/chế biến) | SERVICE (dịch vụ)
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

    # Liên kết với Cửa hàng hiện tại
    store_id = Column(
        Integer,
        ForeignKey("Store.store_id", ondelete="SET NULL"),
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

    role_id = Column(
        Integer,
        ForeignKey("Role.role_id", ondelete="SET NULL"),
        nullable=True
    )

    @property
    def role(self) -> str:
        if self.role_rel and self.role_rel.role_name:
            return self.role_rel.role_name
        return "USER"

    @property
    def store_name(self) -> str | None:
        if self.store_rel and self.store_rel.store_name:
            return self.store_rel.store_name
        return None

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

    @property
    def address_detail(self) -> str | None:
        if self.store_rel and self.store_rel.address_detail:
            return self.store_rel.address_detail
        return None

    failed_attempts = Column(
        Integer,
        default=0,
        nullable=True
    )

    lock_until = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships (User 1-N ...)
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
    categories = relationship(
        "Category",
        back_populates="user"
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user"
    )
    otp_codes = relationship(
        "OTPCode",
        back_populates="user"
    )
    voice_records = relationship(
        "VoiceRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[VoiceRecord.user_id]"
    )
    role_rel = relationship(
        "Role",
        back_populates="users",
        lazy="joined"
    )
    store_rel = relationship(
        "Store",
        foreign_keys=[store_id],
        lazy="joined"
    )
    owned_stores = relationship(
        "Store",
        back_populates="owner",
        foreign_keys="[Store.user_id]",
        cascade="all, delete-orphan"
    )
    