from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, text

from app.configs.database import Base


class AppSetting(Base):
    """
    Cài đặt toàn hệ thống do admin chỉnh trên giao diện (khoá -> JSON).
    Hiện dùng cho khoá "observability": bật / tắt Audit Log theo chức năng, mức chi tiết,
    thời gian giữ log. Giá trị thiếu thì lấy mặc định trong app/services/app_setting_service.py.
    """
    __tablename__ = "App_Setting"

    setting_key = Column(String(64), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_by = Column(Integer, nullable=True)
