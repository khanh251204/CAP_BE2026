from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PermissionItem(BaseModel):
    permission_id: int = Field(..., description="ID quyền")
    code: str = Field(..., description="Mã quyền (vd: user:read, product:create)")
    module: str = Field(..., description="Module (USER, PRODUCT, TRANSACTION...)")
    description: Optional[str] = Field(None, description="Mô tả chức năng")

    class Config:
        from_attributes = True


class RoleItem(BaseModel):
    role_id: int = Field(..., description="ID vai trò")
    role_name: str = Field(..., description="Tên vai trò (ADMIN, OWNER, STAFF...)")
    description: Optional[str] = Field(None, description="Mô tả vai trò")
    is_system: bool = Field(False, description="Vai trò hệ thống không được xóa")
    user_count: int = Field(0, description="Số người dùng thuộc vai trò này")
    permissions: List[PermissionItem] = Field(default_factory=list, description="Danh sách quyền")
    created_at: datetime = Field(..., description="Thời gian tạo")

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    items: List[RoleItem] = Field(..., description="Danh sách các vai trò")
    total: int = Field(..., description="Tổng số vai trò")


class PermissionGroupItem(BaseModel):
    module: str = Field(..., description="Tên nhóm module")
    permissions: List[PermissionItem] = Field(..., description="Danh sách quyền trong module")


class RoleCreateRequest(BaseModel):
    role_name: str = Field(..., min_length=2, max_length=50, description="Tên vai trò mới")
    description: Optional[str] = Field(None, max_length=255, description="Mô tả vai trò")
    permission_ids: List[int] = Field(default_factory=list, description="Danh sách ID quyền được gán")


class RoleUpdateRequest(BaseModel):
    role_name: Optional[str] = Field(None, min_length=2, max_length=50, description="Tên vai trò")
    description: Optional[str] = Field(None, max_length=255, description="Mô tả vai trò")
    permission_ids: Optional[List[int]] = Field(None, description="Danh sách ID quyền được cập nhật")


class AssignUserRoleRequest(BaseModel):
    role_id: int = Field(..., description="ID của vai trò cần gán cho người dùng")
