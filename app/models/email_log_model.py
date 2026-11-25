from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, text
from app.configs.database import Base


class EmailLog(Base):
    """Lịch sử các email hệ thống đã gửi (OTP, gói AI, nhắc hết hạn, gửi thủ công...)."""

    __tablename__ = "Email_Log"

    email_log_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    to_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    email_type = Column(String(50), nullable=False, default="OTHER", index=True)
    status = Column(String(20), nullable=False, default="SENT", index=True)  # SENT | FAILED
    error_message = Column(Text, nullable=True)
    text_body = Column(Text, nullable=True)
    html_body = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=True, index=True)
    sent_by = Column(Integer, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
