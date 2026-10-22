from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship

from app.configs.database import Base


class Store(Base):
    __tablename__ = "Store"

    store_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("User.user_id", ondelete="CASCADE"), nullable=False, index=True)
    store_name = Column(String(255), nullable=False)
    business_type = Column(String(100), nullable=True)  # RESELLER | PRODUCER | SERVICE
    address_detail = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Chủ sở hữu cửa hàng
    owner = relationship("User", back_populates="owned_stores", foreign_keys=[user_id])
