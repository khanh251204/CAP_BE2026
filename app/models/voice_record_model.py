from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    JSON,
    Numeric,
    Float,
    DateTime,
    ForeignKey,
    text
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.configs.database import Base


class VoiceRecord(Base):
    __tablename__ = "Voice_Record"

    voice_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id"),
        nullable=True,
        index=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id"),
        nullable=True,
        index=True
    )

    audio_path = Column(
        String(500),
        nullable=True
    )

    transcript = Column(
        Text,
        nullable=True
    )

    intent = Column(
        String(100),
        nullable=True
    )

    status = Column(
        String(50),
        nullable=True,
        default="SUCCESS"
    )

    confidence = Column(
        Numeric(5, 4),
        nullable=True
    )

    processing_time = Column(
        Float,
        nullable=True
    )

    error_message = Column(
        Text,
        nullable=True
    )

    llm_output = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=text("CURRENT_TIMESTAMP")
    )

    updated_at = Column(
        DateTime,
        nullable=True,
        default=datetime.now,
        onupdate=datetime.now
    )

    # Relationships
    user = relationship(
        "User",
        back_populates="voice_records",
        foreign_keys=[user_id]
    )

    transaction = relationship(
        "Transaction",
        back_populates="voice_records",
        foreign_keys=[transaction_id]
    )
