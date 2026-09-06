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

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id"),
        nullable=False
    )

    audio_path = Column(
        String(255),
        nullable=True
    )

    transcript = Column(
        Text,
        nullable=True
    )

    llm_output = Column(
        JSON,
        nullable=True
    )

    confidence = Column(
        Numeric(5, 4),
        nullable=True
    )

    processing_time = Column(
        Float,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships (theo bảng Mối quan hệ trong ERD)
    transaction = relationship(
        "Transaction",
        back_populates="voice_records"
    )
