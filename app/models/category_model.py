from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Enum
)

from app.configs.database import Base
from sqlalchemy.orm import relationship


class Category(Base):
    __tablename__ = "Category"

    category_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("User.user_id"), nullable=True)
    name = Column(String(255), nullable=False)
    type_category = Column(Enum("INCOME","EXPENSE","TRANFER","REFUND"), nullable=False)
    created_at = Column(DateTime,nullable=False)
        
    transactions = relationship(
            "Transaction",
            back_populates="category"
        )