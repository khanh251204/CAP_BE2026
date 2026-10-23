from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, Query, status

from app.configs.jwt import authorize_roles, authenticate_user
from app.services.admin_notification_service import AdminNotificationService
from app.services.notification_cleanup_service import (
    NotificationCleanupService,
    DEFAULT_NOTIFICATION_RETENTION_DAYS,
)

router = APIRouter(
    prefix="/admin/notifications",
    tags=["Admin - Notifications"],
    dependencies=[Depends(authorize_roles("ADMIN", "admin"))]
)


class NotificationCleanupRequest(BaseModel):
    retention_days: Optional[int] = Field(
        DEFAULT_NOTIFICATION_RETENTION_DAYS,
        ge=1,
        le=365,
        description="Số ngày lưu trữ tối đa (mặc định 14 ngày - 2 tuần). Mọi thông báo quá số ngày này sẽ bị xóa cứng tự động."
    )


@router.post(
    "/cleanup",
    status_code=status.HTTP_200_OK,
    summary="Dọn dẹp xóa cứng thông báo quá hạn (Admin)",
    description=(
        "Xóa cứng vĩnh viễn các thông báo trong Firestore nếu thời gian tạo "
        "đã vượt quá số ngày quy định (mặc định là 14 ngày)."
    )
)
def cleanup_notifications(
    payload: Optional[NotificationCleanupRequest] = None,
    retention_days_query: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="Số ngày lưu trữ (nếu không gửi trong request body)"
    )
):
    days = DEFAULT_NOTIFICATION_RETENTION_DAYS
    if payload and payload.retention_days is not None:
        days = payload.retention_days
    elif retention_days_query is not None:
        days = retention_days_query

    result = NotificationCleanupService.cleanup_expired_notifications(retention_days=days)
    return result


# =====================================================
# SCHEMAS
# =====================================================
class AdminNotificationSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    userId: Optional[str] = Field(
        None,
        description='ID 1 user, hoặc "ALL" để gửi cho tất cả. Bỏ trống = gửi tất cả.'
    )
    userIds: Optional[List[str]] = Field(
        None,
        max_length=500,
        description="Danh sách ID user (gửi riêng cho từng người). Ưu tiên hơn userId."
    )
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    notificationType: Optional[str] = Field("SYSTEM", max_length=50)
    icon: Optional[str] = Field("alert", max_length=50)
    iconColor: Optional[str] = Field("#000000", max_length=20)
    borderColor: Optional[str] = Field("#FF0000", max_length=20)


class AdminNotificationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    notificationType: Optional[str] = Field(None, max_length=50)
    icon: Optional[str] = Field(None, max_length=50)
    iconColor: Optional[str] = Field(None, max_length=20)
    borderColor: Optional[str] = Field(None, max_length=20)


class AdminNotificationBulkDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: List[str] = Field(..., min_length=1, max_length=500)


# =====================================================
# LIST
# =====================================================
@router.get(
    "",
    summary="Danh sách thông báo (Admin)",
    description="Xem tất cả thông báo của mọi user, có phân trang và bộ lọc."
)
def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None, description='Lọc theo user ID (hoặc "ALL")'),
    scope: Optional[Literal["ALL", "PERSONAL", "GLOBAL"]] = Query(
        None, description="PERSONAL: chỉ thông báo cá nhân, GLOBAL: chỉ thông báo chung"
    ),
    type: Optional[str] = Query(None, description="Lọc theo notificationType"),
    search: Optional[str] = Query(None, description="Tìm trong tiêu đề / nội dung"),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
):
    return AdminNotificationService.list_notifications(
        page=page,
        limit=limit,
        user_id=user_id,
        notification_type=type,
        scope=scope,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )


# =====================================================
# STATS
# =====================================================
@router.get("/stats", summary="Thống kê thông báo (Admin)")
def notification_stats():
    return AdminNotificationService.get_stats()


# =====================================================
# SEND
# =====================================================
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Gửi thông báo (Admin)",
    description="Gửi cho 1 user, nhiều user, hoặc tất cả. Thông báo cá nhân sẽ được đẩy push qua FCM."
)
def send_notification(
    data: AdminNotificationSendRequest,
    current_admin: dict = Depends(authenticate_user),
):
    return AdminNotificationService.send_notification(
        data.model_dump(),
        admin_id=current_admin.get("sub"),
    )


# =====================================================
# BULK DELETE
# =====================================================
@router.post("/bulk-delete", summary="Xóa nhiều thông báo (Admin)")
def bulk_delete_notifications(data: AdminNotificationBulkDeleteRequest):
    return AdminNotificationService.bulk_delete(data.ids)


# =====================================================
# DETAIL / UPDATE / DELETE
# =====================================================
@router.get("/{notification_id}", summary="Chi tiết thông báo (Admin)")
def get_notification(notification_id: str):
    return AdminNotificationService.get_notification(notification_id)


@router.patch("/{notification_id}", summary="Sửa thông báo (Admin)")
def update_notification(
    notification_id: str,
    data: AdminNotificationUpdateRequest,
):
    return AdminNotificationService.update_notification(
        notification_id,
        data.model_dump(exclude_none=True),
    )


@router.delete(
    "/{notification_id}",
    summary="Xóa thông báo (Admin)",
    description="Xóa cứng. Với thông báo chung, mọi user đều không còn thấy."
)
def delete_notification(notification_id: str):
    return AdminNotificationService.delete_notification(notification_id)
