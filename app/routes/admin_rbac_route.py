import os
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authenticate_user, require_permission, require_admin_area
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
    tags=["Admin - Role & Permission (RBAC)"],
    dependencies=[Depends(require_admin_area)]
)

# Trang giao diện tĩnh: công khai để hiển thị được form đăng nhập.
# Trang không chứa dữ liệu; mọi dữ liệu được tải qua các API bên dưới (đều yêu cầu quyền).
ui_router = APIRouter(prefix="/admin/rbac", tags=["Admin - Role & Permission (RBAC)"])


@ui_router.get(
    "/ui",
    response_class=HTMLResponse,
    summary="Giao diện Web Admin RBAC Dashboard",
    include_in_schema=True
)
def get_rbac_dashboard_ui():
    """Phục vụ trực tiếp giao diện Web quản trị Ma trận phân quyền RBAC."""
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "admin_rbac.html")
    if os.path.exists(file_path):
        return FileResponse(file_path, headers={
            # Trang quản trị: không cho nhúng iframe (chống clickjacking), không cache
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "frame-ancestors 'none'",
            "Cache-Control": "no-store",
        })
    return HTMLResponse("<h3>Giao diện đang được cập nhật</h3>")


@router.get(
    "/roles",
    response_model=RoleListResponse,
    summary="Danh sách vai trò và phân quyền",
    description="Lấy toàn bộ vai trò, số lượng người dùng thuộc vai trò đó và danh sách quyền tương ứng.",
    dependencies=[Depends(require_permission("rbac:read"))],
)
def list_roles(db: Session = Depends(get_db)):
    return RBACService.get_roles_with_counts(db)


@router.get(
    "/roles/{role_id}",
    response_model=RoleItem,
    summary="Chi tiết vai trò",
    description="Xem thông tin chi tiết một vai trò và các quyền hạn được cấp.",
    dependencies=[Depends(require_permission("rbac:read"))],
)
def get_role_detail(role_id: int, db: Session = Depends(get_db)):
    return RBACService.get_role_detail(db, role_id)


@router.post(
    "/roles",
    response_model=RoleItem,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo vai trò mới",
    description="Tạo vai trò mới và gán danh sách permissions ban đầu.",
    dependencies=[Depends(require_permission("rbac:manage"))],
)
def create_role(
    req: RoleCreateRequest,
    current_user: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    return RBACService.create_role(db, req, actor_id=int(current_user["sub"]))


@router.put(
    "/roles/{role_id}",
    response_model=RoleItem,
    summary="Cập nhật vai trò và ma trận quyền",
    description="Sửa tên, mô tả hoặc cập nhật danh sách các permission_id gán cho vai trò này.",
    dependencies=[Depends(require_permission("rbac:manage"))],
)
def update_role(
    role_id: int,
    req: RoleUpdateRequest,
    current_user: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    return RBACService.update_role(db, role_id, req, actor_id=int(current_user["sub"]))


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa vai trò",
    description="Xóa vai trò (chặn xóa nếu là vai trò hệ thống hoặc đang có người dùng thuộc vai trò này).",
    dependencies=[Depends(require_permission("rbac:manage"))],
)
def delete_role(
    role_id: int,
    current_user: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    RBACService.delete_role(db, role_id, actor_id=int(current_user["sub"]))
    return None


@router.get(
    "/permissions",
    response_model=List[PermissionGroupItem],
    summary="Danh sách quyền theo nhóm module",
    description="Lấy toàn bộ quyền hạn trong hệ thống gom nhóm theo từng Module (USER, PRODUCT, TRANSACTION...).",
    dependencies=[Depends(require_permission("rbac:read"))],
)
def list_permissions(db: Session = Depends(get_db)):
    return RBACService.get_permissions_grouped(db)


@router.put(
    "/users/{user_id}/role",
    summary="Gán vai trò cho người dùng",
    description="Chỉ định vai trò (role_id) cho một người dùng cụ thể.",
    dependencies=[Depends(require_permission("rbac:manage"))],
)
def assign_user_role(
    user_id: int,
    req: AssignUserRoleRequest,
    current_user: dict = Depends(authenticate_user),
    db: Session = Depends(get_db),
):
    return RBACService.assign_user_role(
        db, user_id=user_id, role_id=req.role_id, actor_id=int(current_user["sub"])
    )
