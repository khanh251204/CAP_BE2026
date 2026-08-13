from datetime import datetime, timezone

from app.configs.firebase import db


class NotificationRepository:

    @staticmethod
    def get_all():
        docs = (
            db.collection("notifications")
            .order_by("createdAt", direction="DESCENDING")
            .stream()
        )

        notifications = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            notifications.append(data)

        return notifications

    @staticmethod
    def create(data: dict):
        notification = {
            "description": data.get("description"),
            "userId": data.get("userId"),
            "iconColor": data.get("iconColor", "#000000"),
            "isRead": False,
            "createdAt": datetime.now(timezone.utc),
            "icon": data.get("icon", "alert"),
            "borderColor": data.get("borderColor", "#FF0000"),
            "title": data.get("title"),
            "notificationType": data.get("notificationType", "test")
        }

        doc_ref = db.collection("notifications").document()

        doc_ref.set(notification)

        notification["id"] = doc_ref.id

        return notification

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