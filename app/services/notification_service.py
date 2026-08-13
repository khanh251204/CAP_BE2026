from app.repositories.notification_repository import NotificationRepository


class NotificationService:

    @staticmethod
    def get_all_notifications():
        return NotificationRepository.get_all()

    @staticmethod
    def create_notification(data: dict):
        return NotificationRepository.create(data)

    @staticmethod
    def mark_as_read(notification_id: str):
        return NotificationRepository.mark_as_read(notification_id)