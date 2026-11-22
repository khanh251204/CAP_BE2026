from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class InventoryReasonEnum(str, Enum):
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGE = "DAMAGE"


class ManualInventoryTypeEnum(str, Enum):
    IN = "IN"
    OUT = "OUT"


class ProductTypeEnum(str, Enum):
    RESALE = "RESALE"
    RAW_MATERIAL = "RAW_MATERIAL"
    FINISHED_GOOD = "FINISHED_GOOD"


# ==============================================================================
# PRODUCT REQUEST & RESPONSE SCHEMAS
# ==============================================================================

class ProductCreateRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255, description="Tên sản phẩm")
    default_unit: str = Field(..., min_length=1, max_length=50, description="Đơn vị tính mặc định")
    unit_price: float = Field(..., gt=0, description="Đơn giá bán lẻ (phải > 0)")
    min_quantity: Optional[float] = Field(0.0, ge=0, description="Ngưỡng tồn kho tối thiểu (phải >= 0)")
    product_type: Optional[ProductTypeEnum] = Field(None, description="Loại sản phẩm: RESALE, RAW_MATERIAL, FINISHED_GOOD")
    img: Optional[str] = Field(None, description="Link hình ảnh sản phẩm")
    category_id: Optional[int] = Field(None, description="ID danh mục sản phẩm")

    model_config = ConfigDict(extra="allow")


class ProductUpdateRequest(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tên sản phẩm")
    default_unit: Optional[str] = Field(None, min_length=1, max_length=50, description="Đơn vị tính mặc định")
    unit_price: Optional[float] = Field(None, gt=0, description="Đơn giá bán lẻ")
    min_quantity: Optional[float] = Field(None, ge=0, description="Ngưỡng tồn kho tối thiểu")
    product_type: Optional[ProductTypeEnum] = Field(None, description="Loại sản phẩm: RESALE, RAW_MATERIAL, FINISHED_GOOD")
    is_active: Optional[bool] = Field(None, description="Trạng thái kích hoạt sản phẩm")
    category_id: Optional[int] = Field(None, description="ID danh mục sản phẩm")
    img: Optional[str] = Field(None, description="Link hình ảnh sản phẩm")

    model_config = ConfigDict(extra="allow")


class ProductResponse(BaseModel):
    product_id: int
    user_id: int
    product_name: str
    product_type: str
    default_unit: str
    unit_price: float
    min_quantity: float
    is_active: bool
    category_id: Optional[int] = None
    img: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra="ignore")


# ==============================================================================
# INVENTORY SUB-OPERATION SCHEMAS
# ==============================================================================

class InventoryCheckRequest(BaseModel):
    actual_quantity: float = Field(..., ge=0, description="Số lượng đếm thực tế")
    note: Optional[str] = Field("Kiểm kho định kỳ", description="Ghi chú kiểm kho")
    reason: Optional[InventoryReasonEnum] = Field(InventoryReasonEnum.ADJUSTMENT, description="Lý do điều chỉnh (ADJUSTMENT hoặc DAMAGE)")
    count_unit: Optional[str] = Field(
        None,
        description="Đơn vị của actual_quantity. Bỏ trống = đơn vị tính kho. Đơn vị đóng gói đã khai báo (gói) "
                    "-> đếm gói nguyên, chỉ ghi phần gói lệch, giữ phần gói đang dùng dở",
    )


class ManualInventoryTransactionRequest(BaseModel):
    inventory_type: ManualInventoryTypeEnum = Field(..., description="Loại biến động (IN hoặc OUT)")
    quantity: float = Field(..., gt=0, description="Số lượng biến động (phải > 0)")
    note: Optional[str] = Field(None, description="Ghi chú xuất/nhập kho")


# Backwards compatibility aliases
ProductCreateSchema = ProductCreateRequest
ProductUpdateStrictSchema = ProductUpdateRequest
InventoryCheckRequestSchema = InventoryCheckRequest
ManualInventoryTransactionSchema = ManualInventoryTransactionRequest


# ==============================================================================
# STOCK ALERT SCHEMAS
# ==============================================================================

class StockAlertItem(BaseModel):
    product_id: int
    product_name: str
    product_type: Optional[str] = None
    default_unit: Optional[str] = None
    unit_price: float
    min_quantity: float
    current_stock: float
    total_imported: float
    total_sold: float
    alert_type: str
    alert_message: str
    severity: str


class StockAlertSummary(BaseModel):
    total_alerts: int
    total_out_of_stock: int
    total_low_stock: int


class StockAlertResponse(BaseModel):
    success: bool
    summary: StockAlertSummary
    data: List[StockAlertItem]
