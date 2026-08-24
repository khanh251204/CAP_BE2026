from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text
)

from app.configs.database import Base
from sqlalchemy.orm import relationship

class Supplier(Base):
    __tablename__ = "Supplier"

    supplier_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, 
        ForeignKey("User.user_id"), 
        nullable=True)
    name = Column(String(255), nullable=False)
    phone_number = Column(String(20),nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime,nullable=False)
    updated_at = Column(DateTime, nullable=False)

    transactions = relationship(
            "Transaction",
            back_populates="supplier"
        )
    user = relationship(
            "User",
            back_populates="supplier"
        )
    debt = relationship(
            "Debt",
            back_populates="supplier"
        )