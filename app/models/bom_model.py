from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.configs.database import Base


class BillOfMaterial(Base):
    """
    Định mức nguyên vật liệu (BOM) cho PRODUCER: mỗi dòng là một nguyên liệu của một thành phẩm.
    Ví dụ: 1 tô phở (FINISHED_GOOD) dùng 150 g thịt bò (RAW_MATERIAL).
    """
    __tablename__ = "Bill_Of_Material"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "finished_product_id", "material_product_id",
            name="uq_bom_user_finished_material",
        ),
    )

    bom_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("User.user_id"), nullable=False, index=True)
    finished_product_id = Column(Integer, ForeignKey("Product.product_id"), nullable=False, index=True)
    material_product_id = Column(Integer, ForeignKey("Product.product_id"), nullable=False)

    # Lượng nguyên liệu cho 1 đơn vị thành phẩm, tính theo default_unit của nguyên liệu
    quantity_per_unit = Column(Numeric(15, 4), nullable=False)
    # Snapshot đơn vị nguyên liệu lúc khai báo
    unit = Column(String(50), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
