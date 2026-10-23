from fastapi import HTTPException

from app.services.notification_service import (
    NotificationService
)


class NotificationController:

    @staticmethod
    def get_all_notifications(
        user_id: str
    ):
        return NotificationService.get_all_notifications(
            user_id
        )

    @staticmethod
    def create_notification(
        data: dict
    ):
        return NotificationService.create_notification(
            data
        )

    @staticmethod
    def mark_as_read(
        notification_id: str,
        user_id: str
    ):
        return NotificationService.mark_as_read(
            notification_id,
            user_id
        )

    @staticmethod
    def delete_notification(
        notification_id: str,
        user_id: str
    ):
        result = NotificationService.delete_notification(
            notification_id,
            user_id
        )

        if not result.get("success"):
            status_code = 404 if result.get("code") == "NOT_FOUND" else 403
            raise HTTPException(
                status_code=status_code,
                detail=result.get("message")
            )

        return result

    @staticmethod
    def delete_all_notifications(
        user_id: str
    ):
        return NotificationService.delete_all_notifications(
            user_id
        )
