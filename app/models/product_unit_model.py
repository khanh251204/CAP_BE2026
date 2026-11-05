from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint

from app.configs.database import Base


class ProductUnit(Base):
    """
    Đơn vị quy đổi của sản phẩm (ngoài đơn vị tính kho Product.default_unit).
    Ví dụ mì chính tính kho theo g: 1 gói = 1000 g; coca tính theo lon: 1 thùng = 24 lon.
    Kho luôn ghi theo default_unit; đơn vị quy đổi chỉ dùng khi nhập / bán / khai báo định mức.
    """
    __tablename__ = "Product_Unit"
    __table_args__ = (
        UniqueConstraint("product_id", "unit_name", name="uq_product_unit_name"),
    )

    product_unit_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("User.user_id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("Product.product_id"), nullable=False, index=True)
    unit_name = Column(String(50), nullable=False)
    # Số default_unit trong 1 đơn vị này (1 gói = 1000 g -> 1000)
    factor = Column(Numeric(15, 4), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
