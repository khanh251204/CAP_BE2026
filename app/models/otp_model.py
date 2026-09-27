from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    text
)
from sqlalchemy.orm import relationship

from app.configs.database import Base


class OTPCode(Base):
    __tablename__ = "OTP_Code"

    otp_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=True
    )

    email = Column(
        String(255),
        nullable=False,
        index=True
    )

    otp_hash = Column(
        String(255),
        nullable=False
    )

    # verify_email | forgot_password
    purpose = Column(
        String(50),
        nullable=False
    )

    expires_at = Column(
        DateTime,
        nullable=False
    )

    is_used = Column(
        Boolean,
        nullable=False,
        default=False
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # Thêm trường attempts theo ERD
    attempts = Column(
        Integer,
        default=0,
        nullable=False
    )

    # Relationships (User 1-N OTP_Code)
    user = relationship(
        "User",
        back_populates="otp_codes"
    )