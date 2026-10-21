import os
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authorize_roles, require_permission
from app.services.rbac_service import RBACService
from app.schemas.rbac_schema import (
    RoleListResponse,
    RoleItem,
    PermissionGroupItem,
    RoleCreateRequest,
    RoleUpdateRequest,
    AssignUserRoleRequest,
)

router = APIRouter(
    prefix="/admin/rbac",
    tags=["Admin - Role & Permission (RBAC)"]
)


@router.get(
    "/ui",
    response_class=HTMLResponse,
    summary="Giao diện Web Admin RBAC Dashboard",
    include_in_schema=True
)
def get_rbac_dashboard_ui():
    """Phục vụ trực tiếp giao diện Web quản trị Ma trận phân quyền RBAC."""
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "admin_rbac.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h3>Giao diện đang được cập nhật</h3>")


@router.get(
    "/roles",
    response_model=RoleListResponse,
    summary="Danh sách vai trò và phân quyền",
    description="Lấy toàn bộ vai trò, số lượng người dùng thuộc vai trò đó và danh sách quyền tương ứng."
)
def list_roles(db: Session = Depends(get_db)):
    return RBACService.get_roles_with_counts(db)


@router.get(
    "/roles/{role_id}",
    response_model=RoleItem,
    summary="Chi tiết vai trò",
    description="Xem thông tin chi tiết một vai trò và các quyền hạn được cấp."
)
def get_role_detail(role_id: int, db: Session = Depends(get_db)):
    return RBACService.get_role_detail(db, role_id)


@router.post(
    "/roles",
    response_model=RoleItem,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo vai trò mới",
    description="Tạo vai trò mới và gán danh sách permissions ban đầu."
)
def create_role(req: RoleCreateRequest, db: Session = Depends(get_db)):
    return RBACService.create_role(db, req)


@router.put(
    "/roles/{role_id}",
    response_model=RoleItem,
    summary="Cập nhật vai trò và ma trận quyền",
    description="Sửa tên, mô tả hoặc cập nhật danh sách các permission_id gán cho vai trò này."
)
def update_role(role_id: int, req: RoleUpdateRequest, db: Session = Depends(get_db)):
    return RBACService.update_role(db, role_id, req)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa vai trò",
    description="Xóa vai trò (chặn xóa nếu là vai trò hệ thống hoặc đang có người dùng thuộc vai trò này)."
)
def delete_role(role_id: int, db: Session = Depends(get_db)):
    RBACService.delete_role(db, role_id)
    return None


@router.get(
    "/permissions",
    response_model=List[PermissionGroupItem],
    summary="Danh sách quyền theo nhóm module",
    description="Lấy toàn bộ quyền hạn trong hệ thống gom nhóm theo từng Module (USER, PRODUCT, TRANSACTION...)."
)
def list_permissions(db: Session = Depends(get_db)):
    return RBACService.get_permissions_grouped(db)


@router.post(
    "/users/{user_id}/role",
    summary="Gán vai trò cho người dùng",
    description="Chỉ định vai trò (role_id) cho một người dùng cụ thể."
)
def assign_user_role(user_id: int, req: AssignUserRoleRequest, db: Session = Depends(get_db)):
    return RBACService.assign_user_role(db, user_id=user_id, role_id=req.role_id)
