from fastapi import APIRouter

from app.controllers.notification_controller import NotificationController

router = APIRouter()


@router.get("/notifications")
def get_notifications():
    return NotificationController.get_all_notifications()

@router.post("/notifications")
def create_notification(data: dict):
    return NotificationController.create_notification(data)


@router.patch("/notifications/{notification_id}/read")
def mark_notification_as_read(notification_id: str):
    return NotificationController.mark_as_read(notification_id)