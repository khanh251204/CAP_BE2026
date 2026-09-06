from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Enum
)

from app.configs.database import Base
from sqlalchemy.orm import relationship


class Intent(Base):
    __tablename__ = "Intent"

    intent_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    intent_name = Column(String(100), nullable=False)
    intent_type = Column(Enum("INCOME", "EXPENSE", "TRANFER", "REFUND", "DEBT", "NONE", name="intent_type_enum"), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships (theo bảng Mối quan hệ trong ERD)
    transactions = relationship(
        "Transaction",
        back_populates="intent"
    )