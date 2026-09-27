from typing import Optional, List
from pydantic import BaseModel, Field, root_validator
from datetime import datetime
from enum import Enum


class InventoryReasonEnum(str, Enum):
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGE = "DAMAGE"


class ManualInventoryTypeEnum(str, Enum):
    IN = "IN"
    OUT = "OUT"


class InventoryCheckRequestSchema(BaseModel):
    actual_quantity: float = Field(..., ge=0, description="Số lượng đếm thực tế")
    note: Optional[str] = Field("Kiểm kho định kỳ", description="Ghi chú kiểm kho")
    reason: Optional[InventoryReasonEnum] = Field(InventoryReasonEnum.ADJUSTMENT, description="Lý do điều chỉnh (ADJUSTMENT hoặc DAMAGE)")


class ManualInventoryTransactionSchema(BaseModel):
    inventory_type: ManualInventoryTypeEnum = Field(..., description="Loại biến động (IN hoặc OUT)")
    quantity: float = Field(..., gt=0, description="Số lượng biến động (phải > 0)")
    note: Optional[str] = Field(None, description="Ghi chú xuất/nhập kho")


class ProductTypeEnum(str, Enum):
    RESALE = "RESALE"
    RAW_MATERIAL = "RAW_MATERIAL"
    FINISHED_GOOD = "FINISHED_GOOD"


class ProductCreateSchema(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255, description="Tên sản phẩm")
    default_unit: str = Field(..., min_length=1, max_length=50, description="Đơn vị tính mặc định")
    unit_price: float = Field(..., gt=0, description="Đơn giá bán lẻ (phải > 0)")
    min_quantity: Optional[float] = Field(0.0, ge=0, description="Ngưỡng tồn kho tối thiểu (phải >= 0)")
    product_type: Optional[ProductTypeEnum] = Field(ProductTypeEnum.RESALE, description="Loại sản phẩm: RESALE, RAW_MATERIAL, FINISHED_GOOD")
    img: Optional[str] = Field(None, description="Link hình ảnh sản phẩm")


class ProductUpdateStrictSchema(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    default_unit: Optional[str] = Field(None, min_length=1, max_length=50)
    unit_price: Optional[float] = Field(None, gt=0)
    min_quantity: Optional[float] = Field(None, ge=0)
    product_type: Optional[ProductTypeEnum] = None
    is_active: Optional[bool] = None
    category_id: Optional[int] = None
    img: Optional[str] = None
