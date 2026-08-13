from app.services.notification_service import NotificationService


class NotificationController:

    @staticmethod
    def get_all_notifications():
        return NotificationService.get_all_notifications()

    @staticmethod
    def mark_as_read(notification_id: str):
        return NotificationService.mark_as_read(notification_id)