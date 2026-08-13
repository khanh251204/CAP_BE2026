from app.configs.firebase import db


class NotificationRepository:

    @staticmethod
    def get_all():
        docs = db.collection("notifications").stream()

        notifications = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            notifications.append(data)

        return notifications

    @staticmethod
    def mark_as_read(notification_id: str):
        doc_ref = db.collection("notifications").document(notification_id)

        doc_ref.update({
            "isRead": True
        })

        return {
            "id": notification_id,
            "isRead": True
        }