from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum
)

from app.configs.database import Base
from sqlalchemy.orm import relationship

class Intent(Base):
    __tablename__ = "Intent"

    intent_id = Column(Integer, primary_key=True, index=True)
    name_intent = Column(String(255), nullable=False)
    type = Column(Enum('INCOME','EXPENSE','DEBT','TRANFER','REFUND'))
    description = Column(String(255), nullable=False)
    transactions = relationship(
            "Transaction",
            back_populates="intent"
        )