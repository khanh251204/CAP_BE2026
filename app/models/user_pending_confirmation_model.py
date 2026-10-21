from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    text
)
from app.configs.database import Base


class UserPendingConfirmation(Base):
    __tablename__ = "User_Pending_Confirmation"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    session_key = Column(
        String(120),
        unique=True,
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    intent = Column(
        String(100),
        nullable=True
    )

    payload_json = Column(
        Text,
        nullable=False
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

    expires_at = Column(
        DateTime,
        nullable=False,
        index=True
    )
