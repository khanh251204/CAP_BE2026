import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    JSON,
    Float,
    DateTime,
    ForeignKey,
    Enum,
    Index,
    text
)
from sqlalchemy.orm import relationship

from app.configs.database import Base


class SystemLogLevel(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class SystemLogStep(str, enum.Enum):
    AUTH = "AUTH"
    STT = "STT"
    LLM = "LLM"
    DB = "DB"
    OTHER = "OTHER"


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        index=True,
        server_default=text("CURRENT_TIMESTAMP")
    )

    level = Column(
        Enum("INFO", "WARNING", "ERROR", name="system_log_level_enum"),
        nullable=False,
        default="INFO",
        index=True
    )

    step = Column(
        Enum("AUTH", "STT", "LLM", "DB", "OTHER", name="system_log_step_enum"),
        nullable=True,
        default="OTHER",
        index=True
    )

    api_path = Column(
        String(255),
        nullable=True
    )

    http_method = Column(
        String(10),
        nullable=True
    )

    status_code = Column(
        Integer,
        nullable=True
    )

    duration_ms = Column(
        Float,
        nullable=True
    )

    message = Column(
        Text,
        nullable=True
    )

    detail = Column(
        JSON,
        nullable=True
    )

    request_id = Column(
        String(64),
        nullable=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    device = Column(
        JSON,
        nullable=True
    )

    app_version = Column(
        String(50),
        nullable=True
    )

    # Relationships
    user = relationship("User", backref="system_logs")

    # Composite index for rapid query & metrics
    __table_args__ = (
        Index("ix_system_logs_created_at_level", "created_at", "level"),
    )
