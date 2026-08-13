from app.repositories.notification_repository import NotificationRepository


class NotificationService:

    @staticmethod
    def get_all_notifications():
        return NotificationRepository.get_all()

    @staticmethod
    def mark_as_read(notification_id: str):
        return NotificationRepository.mark_as_read(notification_id)