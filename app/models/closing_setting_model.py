from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    Enum,
    Time,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime, time

from app.configs.database import Base


class ClosingSetting(Base):
    __tablename__ = "closing_setting"

    setting_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    period_type = Column(
        Enum("DAY", "MONTH", "QUARTER", "YEAR", name="closing_setting_period_type_enum"),
        nullable=False,
        default="DAY"
    )

    closing_time = Column(
        Time,
        nullable=False,
        default=time(23, 0, 0)
    )

    auto_close = Column(
        Boolean,
        nullable=False,
        default=False
    )

    send_report = Column(
        Boolean,
        nullable=False,
        default=True
    )

    report_channel = Column(
        Enum("EMAIL", name="closing_report_channel_enum"),
        nullable=False,
        default="EMAIL"
    )

    timezone = Column(
        String(64),
        nullable=False,
        default="Asia/Ho_Chi_Minh"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now
    )

    # Relationships
    user = relationship("User", backref="closing_settings")
