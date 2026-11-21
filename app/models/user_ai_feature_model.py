from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, text

from app.configs.database import Base


class UserAIFeature(Base):
    """
    Cấu hình tính năng AI & danh sách intent được phép theo từng tài khoản (User).

    - `allowed_intents is None`: không giới hạn (mặc định dùng đầy đủ 17 intents — tương thích ngược).
    - `allowed_intents == []`: khóa toàn bộ AI intent (không gọi LLM, tiết kiệm 100% token).
    - `allowed_intents == ["ban_hang", "mua_hang"]`: chỉ cho phép đúng các intent này và
      tự động rút gọn system prompt gửi lên LLM để giảm token + thời gian phản hồi.
    """

    __tablename__ = "User_AI_Feature"

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    plan_code = Column(String(64), nullable=True, index=True)
    allowed_intents = Column(JSON, nullable=True)
    allow_multi_item = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    allow_ocr = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    note = Column(String(255), nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_by = Column(Integer, nullable=True)
