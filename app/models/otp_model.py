from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    text
)

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

    attempts = Column(
        Integer,
        nullable=False,
        default=0
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
