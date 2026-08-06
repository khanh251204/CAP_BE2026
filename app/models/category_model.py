from sqlalchemy import Column, Integer, String, ForeignKey
from app.configs.database import Base


class Category(Base):
    __tablename__ = "Category"

    category_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("User.user_id"), nullable=True)
    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)