from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from typing import Optional

from app.controllers.notification_controller import NotificationController
from app.configs.jwt import authenticate_user, authorize_roles

router = APIRouter()


class NotificationCreateSchema(BaseModel):
    userId: Optional[str] = "ALL"
    title: str
    description: str
    notificationType: Optional[str] = "SYSTEM"
    icon: Optional[str] = "alert"
    iconColor: Optional[str] = "#000000"
    borderColor: Optional[str] = "#FF0000"


# GET
@router.get("/notifications")
def get_notifications(
    payload: dict = Depends(authenticate_user)
):
    user_id = payload.get("sub")

    return NotificationController.get_all_notifications(
        user_id=str(user_id)
    )


# CREATE (Yêu cầu quyền ADMIN - Trả 401 nếu chưa login/invalid token, 403 nếu user thường)
@router.post(
    "/notifications",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(authorize_roles("ADMIN", "admin"))]
)
def create_notification(
    data: NotificationCreateSchema
):
    return NotificationController.create_notification(
        data.dict()
    )


# MARK AS READ
@router.put(
    "/notifications/{notification_id}/read"
)
def mark_notification_as_read(
    notification_id: str,
    payload: dict = Depends(authenticate_user)
):
    user_id = payload.get("sub")

    return NotificationController.mark_as_read(
        notification_id,
        str(user_id)
    )


class FCMTokenRegisterSchema(BaseModel):
    fcmToken: str
    deviceType: Optional[str] = "mobile"


# REGISTER FCM TOKEN
@router.post("/notifications/fcm-token")
def register_fcm_token(
    data: FCMTokenRegisterSchema,
    payload: dict = Depends(authenticate_user)
):
    user_id = payload.get("sub")
    from app.services.fcm_service import FCMService
    success = FCMService.register_device_token(
        user_id=str(user_id),
        fcm_token=data.fcmToken,
        device_type=data.deviceType
    )
    return {
        "success": success,
        "message": "Đã lưu FCM device token thành công" if success else "Lưu token thất bại"
    }

# DELETE ALL (của user hiện tại)
@router.delete("/notifications")
def delete_all_notifications(
    payload: dict = Depends(authenticate_user)
):
    user_id = payload.get("sub")

    return NotificationController.delete_all_notifications(
        str(user_id)
    )


# DELETE ONE
@router.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: str,
    payload: dict = Depends(authenticate_user)
):
    user_id = payload.get("sub")

    return NotificationController.delete_notification(
        notification_id,
        str(user_id)
    )
