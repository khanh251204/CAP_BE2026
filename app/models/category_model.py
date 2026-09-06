from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Enum,
    text
)
from sqlalchemy.orm import relationship, synonym
from datetime import datetime

from app.configs.database import Base


class Category(Base):
    __tablename__ = "Category"

    category_id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("User.user_id"), nullable=True)
    category_name = Column(String(255), nullable=False)
    
    # Giới hạn đúng 3 giá trị theo ERD: 'INCOME', 'EXPENSE', 'TRANFER'
    category_type = Column(
        Enum("INCOME", "EXPENSE", "TRANFER", name="category_type_enum"),
        nullable=False
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    # Synonyms for backward compatibility
    name = synonym("category_name")
    type_category = synonym("category_type")

    # Relationships (theo bảng Mối quan hệ trong ERD)
    user = relationship(
        "User",
        back_populates="categories"
    )
    transactions = relationship(
        "Transaction",
        back_populates="category"
    )