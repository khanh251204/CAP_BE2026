from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authenticate_user, require_permission, require_admin_area
from app.schemas.admin_user_schema import (
    AdminUserListResponse,
    AdminUserDetailResponse,
    AdminUserStatusUpdateRequest,
    AdminUserStatusUpdateResponse,
)
from app.services.admin_user_service import AdminUserService

router = APIRouter(
    prefix="/admin/users",
    tags=["Admin - User Management"],
    dependencies=[Depends(require_admin_area)]
)


@router.get(
    "",
    response_model=AdminUserListResponse,
    summary="Xem danh sách người dùng",
    description="Truy vấn danh sách người dùng với phân trang, tìm kiếm theo tên/email/SĐT và bộ lọc theo vai trò (role), trạng thái (status), loại hình kinh doanh (business_type) và ngày tạo.",
    dependencies=[Depends(require_permission("admin_user:read"))],
)
def list_users(
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi trên một trang (1 đến 100)"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm trong họ tên, email, SĐT hoặc tên cửa hàng"),
    role: Optional[str] = Query(None, description="Lọc theo vai trò: admin, user, owner, staff"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái tài khoản: ACTIVE, LOCKED, UNVERIFIED"),
    business_type: Optional[str] = Query(None, description="Lọc theo loại hình kinh doanh: RESELLER, PRODUCER, SERVICE"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Thời điểm tạo bắt đầu (ISO 8601)"),
    to_date: Optional[datetime] = Query(None, alias="to", description="Thời điểm tạo kết thúc (ISO 8601)"),
    db: Session = Depends(get_db)
):
    return AdminUserService.list_users(
        db=db,
        page=page,
        limit=limit,
        search=search,
        role=role,
        status_filter=status,
        business_type=business_type,
        from_date=from_date,
        to_date=to_date
    )


@router.get(
    "/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Xem thông tin chi tiết một người dùng",
    description="Truy xuất đầy đủ thông tin chi tiết của người dùng theo ID, bao gồm định danh, liên hệ, loại hình kinh doanh, địa chỉ, trạng thái tài khoản. Tuyệt đối không trả về mật khẩu hay thông tin nhạy cảm.",
    dependencies=[Depends(require_permission("admin_user:read"))],
)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db)
):
    return AdminUserService.get_user_detail(db=db, user_id=user_id)


@router.patch(
    "/{user_id}/status",
    response_model=AdminUserStatusUpdateResponse,
    summary="Khóa hoặc mở khóa tài khoản người dùng",
    description="Cho phép Admin khóa hoặc mở khóa tài khoản người dùng. Khi khóa, thời gian lock_until được thiết lập và toàn bộ refresh token hiện có của người dùng sẽ bị vô hiệu hóa.",
    dependencies=[Depends(require_permission("admin_user:manage"))],
)
def update_user_status(
    user_id: int,
    request: AdminUserStatusUpdateRequest,
    current_admin: dict = Depends(authenticate_user),
    db: Session = Depends(get_db)
):
    admin_id = int(current_admin.get("sub", 0))
    return AdminUserService.update_user_status(
        db=db,
        user_id=user_id,
        current_admin_id=admin_id,
        request=request
    )
