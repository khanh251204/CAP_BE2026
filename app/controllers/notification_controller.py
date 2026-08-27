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
