from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    DateTime,
    ForeignKey,
    text
)
from sqlalchemy.orm import relationship

from app.configs.database import Base


class UserCorrection(Base):
    """
    Bảng lưu vết hiệu chỉnh của người dùng (Human-in-the-Loop) trong quá trình xác nhận giao dịch AI.
    Phục vụ:
      - Đối chiếu Ground Truth vs AI Prediction
      - Lưu trữ dữ liệu nghiên cứu & đánh giá lỗi (Error Analysis)
      - Phục vụ Ingestion vào Data Lake / Dataset
    """
    __tablename__ = "User_Correction"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    voice_record_id = Column(
        Integer,
        ForeignKey("Voice_Record.voice_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    correction_type = Column(
        String(50),
        nullable=True,
        default="MANUAL_EDIT"
    )

    original_ai_result = Column(
        JSON,
        nullable=True
    )

    corrected_result = Column(
        JSON,
        nullable=True
    )

    diff = Column(
        JSON,
        nullable=True
    )

    extra_metadata = Column(
        JSON,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True
    )

    # Relationships
    user = relationship(
        "User",
        backref="user_corrections",
        foreign_keys=[user_id]
    )

    voice_record = relationship(
        "VoiceRecord",
        backref="user_corrections",
        foreign_keys=[voice_record_id]
    )

    transaction = relationship(
        "Transaction",
        backref="user_corrections",
        foreign_keys=[transaction_id]
    )
