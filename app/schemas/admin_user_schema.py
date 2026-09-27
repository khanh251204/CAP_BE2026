from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AdminUserPagination(BaseModel):
    page: int = Field(..., description="Trang hiện tại (1-based)")
    limit: int = Field(..., description="Số bản ghi trên mỗi trang")
    total: int = Field(..., description="Tổng số bản ghi thỏa mãn điều kiện lọc")
    total_pages: int = Field(..., description="Tổng số trang")


class AdminUserListItem(BaseModel):
    id: int = Field(..., description="ID người dùng")
    user_id: int = Field(..., description="ID người dùng (alias)")
    full_name: str = Field(..., description="Họ và tên")
    email: str = Field(..., description="Email đăng nhập")
    phone_number: Optional[str] = Field(None, description="Số điện thoại")
    role: str = Field(..., description="Vai trò: admin, user, owner, staff")
    status: str = Field(..., description="Trạng thái tài khoản: ACTIVE, LOCKED, UNVERIFIED")
    business_type: Optional[str] = Field(None, description="Loại hình kinh doanh: RESELLER, PRODUCER, SERVICE")
    account_type: Optional[str] = Field("personal", description="Loại tài khoản: personal, business")
    store_name: Optional[str] = Field(None, description="Tên cửa hàng")
    region: Optional[str] = Field(None, description="Vùng miền / Tỉnh thành")
    is_verified: bool = Field(False, description="Trạng thái xác thực email")
    lock_until: Optional[datetime] = Field(None, description="Thời điểm hết hạn khóa tài khoản")
    created_at: datetime = Field(..., description="Thời gian tạo tài khoản")


class AdminUserListResponse(BaseModel):
    items: List[AdminUserListItem] = Field(..., description="Danh sách người dùng")
    pagination: AdminUserPagination = Field(..., description="Thông tin phân trang")


class AdminUserDetailResponse(BaseModel):
    id: int = Field(..., description="ID người dùng")
    user_id: int = Field(..., description="ID người dùng (alias)")
    full_name: str = Field(..., description="Họ và tên")
    email: str = Field(..., description="Email đăng nhập")
    phone_number: Optional[str] = Field(None, description="Số điện thoại")
    role: str = Field(..., description="Vai trò: admin, user, owner, staff")
    status: str = Field(..., description="Trạng thái tài khoản: ACTIVE, LOCKED, UNVERIFIED")
    business_type: Optional[str] = Field(None, description="Loại hình kinh doanh: RESELLER, PRODUCER, SERVICE")
    account_type: Optional[str] = Field("personal", description="Loại tài khoản: personal, business")
    store_name: Optional[str] = Field(None, description="Tên cửa hàng")
    region: Optional[str] = Field(None, description="Vùng miền / Tỉnh thành")
    province_code: Optional[str] = Field(None, description="Mã tỉnh/thành")
    ward_code: Optional[str] = Field(None, description="Mã phường/xã")
    ward_name: Optional[str] = Field(None, description="Tên phường/xã")
    address_detail: Optional[str] = Field(None, description="Địa chỉ chi tiết")
    is_verified: bool = Field(False, description="Trạng thái xác thực email")
    failed_attempts: Optional[int] = Field(0, description="Số lần đăng nhập thất bại")
    lock_until: Optional[datetime] = Field(None, description="Thời điểm hết hạn khóa tài khoản")
    created_at: datetime = Field(..., description="Thời gian tạo tài khoản")


class AdminUserStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Trạng thái mới: LOCKED, ACTIVE, UNLOCKED")
    reason: Optional[str] = Field(None, description="Lý do khóa / mở khóa tài khoản")


class AdminUserStatusUpdateResponse(BaseModel):
    success: bool = Field(True, description="Thao tác thành công")
    message: str = Field(..., description="Thông điệp phản hồi")
    user_id: int = Field(..., description="ID người dùng được cập nhật")
    status: str = Field(..., description="Trạng thái sau khi cập nhật")
    lock_until: Optional[datetime] = Field(None, description="Thời điểm hết hạn khóa tài khoản (nếu có)")
