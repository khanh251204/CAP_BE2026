from app.repositories.notification_repository import (
    NotificationRepository
)


class NotificationService:

    @staticmethod
    def get_all_notifications(
        user_id: str
    ):
        return NotificationRepository.get_all(
            user_id
        )

    @staticmethod
    def create_notification(
        data: dict
    ):
        notif = NotificationRepository.create(
            data
        )
        # Tự động đẩy Push Notification qua FCM tới điện thoại của User
        try:
            target_user = data.get("userId")
            if target_user and str(target_user).upper() != "ALL":
                from app.services.fcm_service import FCMService
                title = data.get("title", "VoiceCashBook")
                body = data.get("description", "")
                FCMService.send_push_to_user(
                    user_id=target_user,
                    title=title,
                    body=body,
                    data={
                        "notificationId": str(notif.get("id", "")),
                        "notificationType": str(data.get("notificationType", "SYSTEM")),
                    }
                )
        except Exception:
            pass

        return notif

    @staticmethod
    def mark_as_read(
        notification_id: str,
        user_id: str
    ):
        return NotificationRepository.mark_as_read(
            notification_id,
            user_id
        )

    @staticmethod
    def delete_notification(
        notification_id: str,
        user_id: str
    ):
        return NotificationRepository.delete_for_user(
            notification_id,
            user_id
        )

    @staticmethod
    def delete_all_notifications(
        user_id: str
    ):
        return NotificationRepository.delete_all_for_user(
            user_id
        )
