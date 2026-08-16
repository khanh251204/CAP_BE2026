from datetime import datetime, timezone
from google.cloud.firestore import Query
from app.configs.firebase import db


class NotificationRepository:

    # =====================================================
    # GET ALL NOTIFICATIONS (Cá nhân + Tất cả mọi người)
    # =====================================================
    @staticmethod
    def get_all(user_id: str):
        str_user_id = str(user_id)

        # 1. Lấy thông báo gửi riêng cho cá nhân
        personal_docs = (
            db.collection("notifications")
            .where("userId", "==", str_user_id)
            .stream()
        )

        # 2. Lấy thông báo gửi chung cho tất cả
        global_docs = (
            db.collection("notifications")
            .where("userId", "==", "ALL")
            .stream()
        )

        notifications = []

        # Xử lý thông báo cá nhân
        for doc in personal_docs:
            data = doc.to_dict()
            data["id"] = doc.id
            notifications.append(data)

        # Xử lý thông báo chung (Tính toán isRead động cho user hiện tại)
        for doc in global_docs:
            data = doc.to_dict()
            data["id"] = doc.id
            
            # Kiểm tra xem user này đã nằm trong mảng readByUsers chưa
            read_by = data.get("readByUsers", [])
            data["isRead"] = str_user_id in read_by
            
            notifications.append(data)

        # Sắp xếp danh sách theo thời gian tạo (mới nhất lên đầu)
        notifications.sort(
            key=lambda x: x.get("createdAt") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        return notifications

    # =====================================================
    # CREATE NOTIFICATION
    # =====================================================
    @staticmethod
    def create(data: dict):
        user_id = data.get("userId")
        
        # Nếu không có userId hoặc userId rỗng -> Coi như gửi cho tất cả (ALL)
        if not user_id or str(user_id).strip() == "" or str(user_id).upper() == "ALL":
            target_user = "ALL"
        else:
            target_user = str(user_id)

        notification = {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "userId": target_user,
            "isRead": False,  # Dùng cho thông báo cá nhân
            "readByUsers": [],  # Dùng chứa danh sách userId đã đọc (Cho thông báo ALL)
            "createdAt": datetime.now(timezone.utc),
            "notificationType": data.get("notificationType", "SYSTEM"),
            "icon": data.get("icon", "alert"),
            "iconColor": data.get("iconColor", "#000000"),
            "borderColor": data.get("borderColor", "#FF0000"),
        }

        doc_ref = db.collection("notifications").document()
        doc_ref.set(notification)

        notification["id"] = doc_ref.id
        return notification

    # =====================================================
    # MARK AS READ
    # =====================================================
    @staticmethod
    def mark_as_read(notification_id: str, user_id: str):
        str_user_id = str(user_id)
        doc_ref = db.collection("notifications").document(notification_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()

        # Nếu là thông báo gửi chung cho tất cả
        if data.get("userId") == "ALL":
            read_by = data.get("readByUsers", [])
            if str_user_id not in read_by:
                read_by.append(str_user_id)
                doc_ref.update({"readByUsers": read_by})
        else:
            # Thông báo cá nhân
            doc_ref.update({"isRead": True})

        return {
            "id": notification_id,
            "isRead": True
        }