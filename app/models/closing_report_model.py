from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.configs.database import Base


class ClosingReport(Base):
    __tablename__ = "closing_report"

    report_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True
    )

    closing_id = Column(
        BigInteger,
        ForeignKey("closing_period.closing_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    report_type = Column(
        Enum("CLOSING_SUMMARY", "EMAIL_SUMMARY", "PDF", name="closing_report_type_enum"),
        nullable=False,
        default="CLOSING_SUMMARY"
    )

    recipient_email = Column(
        String(255),
        nullable=False
    )

    send_status = Column(
        Enum("PENDING", "SENT", "FAILED", name="closing_send_status_enum"),
        nullable=False,
        default="PENDING"
    )

    sent_at = Column(
        DateTime,
        nullable=True
    )

    error_message = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    # Relationships
    closing_period = relationship("ClosingPeriod", back_populates="closing_reports")
    user = relationship("User", backref="closing_reports")
