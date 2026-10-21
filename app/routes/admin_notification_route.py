from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, status

from app.configs.jwt import authorize_roles
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
        description="Số ngày lưu trữ tối đa (mặc định 14 ngày - 2 tuần). Thông báo chưa đọc quá số ngày này sẽ bị xóa cứng."
    )


@router.post(
    "/cleanup",
    status_code=status.HTTP_200_OK,
    summary="Dọn dẹp xóa cứng thông báo quá hạn (Admin)",
    description=(
        "Xóa cứng vĩnh viễn các thông báo trong Firestore nếu cả chưa xem lẫn chưa đọc "
        "và thời gian tạo đã vượt quá số ngày quy định (mặc định là 14 ngày)."
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
