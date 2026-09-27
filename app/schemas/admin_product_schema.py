"""
Admin Product Management — Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AdminProductPagination(BaseModel):
    page: int = Field(..., description="Trang hiện tại (bắt đầu từ 1)")
    limit: int = Field(..., description="Số bản ghi trên mỗi trang")
    total: int = Field(..., description="Tổng số bản ghi thỏa mãn điều kiện")
    total_pages: int = Field(..., description="Tổng số trang")


class AdminProductOwnerInfo(BaseModel):
    user_id: int = Field(..., description="ID chủ sở hữu sản phẩm")
    full_name: str = Field(..., description="Họ và tên người dùng")
    name: Optional[str] = Field(None, description="Họ và tên người dùng (alias)")
    email: str = Field(..., description="Email người dùng")
    phone_number: Optional[str] = Field(None, description="Số điện thoại")
    store_name: Optional[str] = Field(None, description="Tên cửa hàng")
    business_type: Optional[str] = Field(None, description="Loại hình kinh doanh (RESELLER, PRODUCER, SERVICE)")
    role: Optional[str] = Field(None, description="Vai trò tài khoản (user, admin, owner)")


class AdminProductListItem(BaseModel):
    product_id: int = Field(..., description="ID sản phẩm")
    user_id: int = Field(..., description="ID người dùng sở hữu")
    user: Optional[AdminProductOwnerInfo] = Field(None, description="Thông tin người dùng sở hữu")
    owner: Optional[AdminProductOwnerInfo] = Field(None, description="Thông tin chủ sở hữu sản phẩm (alias của user)")
    owner_name: Optional[str] = Field(None, description="Tên chủ sở hữu sản phẩm")
    user_name: Optional[str] = Field(None, description="Tên người dùng sở hữu (alias)")
    owner_email: Optional[str] = Field(None, description="Email chủ sở hữu")
    owner_phone: Optional[str] = Field(None, description="Số điện thoại chủ sở hữu")
    store_name: Optional[str] = Field(None, description="Tên cửa hàng của chủ sở hữu")
    business_type: Optional[str] = Field(None, description="Loại hình kinh doanh của chủ sở hữu")
    product_name: str = Field(..., description="Tên sản phẩm")
    product_type: Optional[str] = Field("RESALE", description="Loại sản phẩm (RESALE, RAW_MATERIAL, FINISHED_GOOD)")
    img: Optional[str] = Field(None, description="URL hình ảnh sản phẩm")
    default_unit: Optional[str] = Field(None, description="Đơn vị tính mặc định")
    unit_price: float = Field(..., description="Đơn giá bán lẻ")
    min_quantity: Optional[float] = Field(0.0, description="Ngưỡng tồn kho tối thiểu")
    is_active: bool = Field(True, description="Trạng thái hoạt động (True = Active, False = Inactive)")
    stock_quantity: float = Field(0.0, description="Tồn kho thực tế hiện tại")
    created_at: Optional[datetime] = Field(None, description="Thời điểm tạo")
    updated_at: Optional[datetime] = Field(None, description="Thời điểm cập nhật")


class AdminProductListResponse(BaseModel):
    items: List[AdminProductListItem] = Field(..., description="Danh sách sản phẩm")
    pagination: AdminProductPagination = Field(..., description="Thông tin phân trang")


class AdminProductDetailResponse(AdminProductListItem):
    total_imported: float = Field(0.0, description="Tổng số lượng đã nhập kho")
    total_sold: float = Field(0.0, description="Tổng số lượng đã bán/xuất kho")
    transaction_count: int = Field(0, description="Tổng số dòng chi tiết giao dịch phát sinh")


class AdminProductStatusUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="Trạng thái kích hoạt mới (True = Hoạt động, False = Ngừng kinh doanh)")


class AdminProductStatusUpdateResponse(BaseModel):
    success: bool = Field(True, description="Kết quả thực hiện")
    message: str = Field(..., description="Thông điệp thông báo")
    product_id: int = Field(..., description="ID sản phẩm")
    is_active: bool = Field(..., description="Trạng thái mới sau khi cập nhật")
