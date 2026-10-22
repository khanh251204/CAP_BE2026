from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


class InventoryItemPayload(BaseModel):
    product_id: Optional[int] = Field(None, description="ID sản phẩm")
    product_name: Optional[str] = Field(None, description="Tên sản phẩm")
    quantity: float = Field(1.0, gt=0, description="Số lượng biến động")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    unit_price: Optional[float] = Field(None, ge=0, description="Đơn giá")

    model_config = ConfigDict(extra="allow")


class InventoryImportRequest(BaseModel):
    items: Optional[List[InventoryItemPayload]] = Field(None, description="Danh sách sản phẩm nhập kho")
    product_id: Optional[int] = Field(None, description="ID sản phẩm (nếu nhập đơn lẻ)")
    product_name: Optional[str] = Field(None, description="Tên sản phẩm (nếu nhập đơn lẻ)")
    quantity: Optional[float] = Field(None, gt=0, description="Số lượng nhập")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    unit_price: Optional[float] = Field(None, ge=0, description="Đơn giá nhập")
    supplier_id: Optional[int] = Field(None, description="ID nhà cung cấp")
    supplier_name: Optional[str] = Field(None, description="Tên nhà cung cấp")
    amount_paid: Optional[float] = Field(None, ge=0, description="Số tiền đã thanh toán")
    account_id: Optional[int] = Field(None, description="ID tài khoản nguồn tiền")
    note: Optional[str] = Field(None, description="Ghi chú nhập hàng")
    input_method: Optional[str] = Field("MANUAL", description="Phương thức nhập: MANUAL hoặc VOICE")

    model_config = ConfigDict(extra="allow")


class InventorySellRequest(BaseModel):
    items: Optional[List[InventoryItemPayload]] = Field(None, description="Danh sách sản phẩm xuất bán")
    product_id: Optional[int] = Field(None, description="ID sản phẩm (nếu bán đơn lẻ)")
    product_name: Optional[str] = Field(None, description="Tên sản phẩm (nếu bán đơn lẻ)")
    quantity: Optional[float] = Field(None, gt=0, description="Số lượng bán")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    unit_price: Optional[float] = Field(None, ge=0, description="Đơn giá bán")
    customer_id: Optional[int] = Field(None, description="ID khách hàng")
    customer_name: Optional[str] = Field(None, description="Tên khách hàng")
    amount_paid: Optional[float] = Field(None, ge=0, description="Số tiền khách đã trả")
    payment_status: Optional[str] = Field(None, description="Trạng thái thanh toán: PAID, PARTIAL, PENDING")
    account_id: Optional[int] = Field(None, description="ID tài khoản nhận tiền")
    note: Optional[str] = Field(None, description="Ghi chú bán hàng")
    input_method: Optional[str] = Field("MANUAL", description="Phương thức: MANUAL hoặc VOICE")

    model_config = ConfigDict(extra="allow")


class InventoryCheckStockRequest(BaseModel):
    product_id: Optional[int] = Field(None, description="ID sản phẩm cần kiểm tra")
    product_name: Optional[str] = Field(None, description="Tên sản phẩm cần kiểm tra")

    model_config = ConfigDict(extra="allow")
