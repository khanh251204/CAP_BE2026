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


class RefreshToken(Base):
    __tablename__ = "Refresh_Token"

    token_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=False,
        index=True
    )

    # JWT ID - định danh duy nhất của refresh token
    jti = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    # SHA256 của refresh token
    token_hash = Column(
        String(255),
        nullable=False
    )

    expires_at = Column(
        DateTime,
        nullable=False
    )

    is_revoked = Column(
        Boolean,
        nullable=False,
        default=False
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    revoked_at = Column(
        DateTime,
        nullable=True
    )

    # Relationships (User 1-N Refresh_Token)
    user = relationship(
        "User",
        back_populates="refresh_tokens"
    )