from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime
from app.configs.database import Base


class Product(Base):
    __tablename__ = "Product"

    product_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    default_unit = Column(String(50))
    min_quantity = Column(Numeric(15, 2))
    is_active = Column(Boolean)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)