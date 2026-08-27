from datetime import datetime, timezone
from app.configs.firebase import db


class NotificationRepository:

    # =====================================================
    # GET ALL NOTIFICATIONS
    # =====================================================
    @staticmethod
    def get_all(user_id: str):
        str_user_id = str(user_id)

        # Thông báo cá nhân
        personal_docs = (
            db.collection("notifications")
            .where("userId", "==", str_user_id)
            .stream()
        )

        # Thông báo cho tất cả
        global_docs = (
            db.collection("notifications")
            .where("userId", "==", "ALL")
            .stream()
        )

        notifications = []

        # =================================================
        # PERSONAL
        # =================================================
        for doc in personal_docs:
            data = doc.to_dict()

            data["id"] = doc.id

            # Đảm bảo luôn có isRead
            data["isRead"] = bool(
                data.get("isRead", False)
            )

            notifications.append(data)

        # =================================================
        # GLOBAL
        # =================================================
        for doc in global_docs:
            data = doc.to_dict()

            data["id"] = doc.id

            read_by = data.get(
                "readByUsers",
                []
            )

            if not isinstance(read_by, list):
                read_by = []

            read_by = [
                str(uid)
                for uid in read_by
            ]

            data["isRead"] = (
                str_user_id in read_by
            )

            notifications.append(data)

        # =================================================
        # SORT
        # =================================================
        notifications.sort(
            key=lambda x:
                x.get("createdAt")
                or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
            reverse=True
        )

        return notifications

    # =====================================================
    # CREATE NOTIFICATION
    # =====================================================
    @staticmethod
    def create(data: dict):

        user_id = data.get("userId")

        if (
            not user_id
            or str(user_id).strip() == ""
            or str(user_id).upper() == "ALL"
        ):
            target_user = "ALL"
        else:
            target_user = str(user_id)

        notification = {
            "title": data.get(
                "title",
                ""
            ),

            "description": data.get(
                "description",
                ""
            ),

            "userId": target_user,

            # Notification cá nhân
            "isRead": False,

            # Notification ALL
            "readByUsers": [],

            "createdAt": datetime.now(
                timezone.utc
            ),

            "notificationType": data.get(
                "notificationType",
                "SYSTEM"
            ),

            "icon": data.get(
                "icon",
                "alert"
            ),

            "iconColor": data.get(
                "iconColor",
                "#000000"
            ),

            "borderColor": data.get(
                "borderColor",
                "#FF0000"
            ),
        }

        doc_ref = (
            db.collection("notifications")
            .document()
        )

        doc_ref.set(notification)

        notification["id"] = doc_ref.id

        return notification

    # =====================================================
    # MARK AS READ
    # =====================================================
    @staticmethod
    def mark_as_read(
        notification_id: str,
        user_id: str
    ):
        str_user_id = str(user_id)

        # =================================================
        # LẤY DOCUMENT
        # =================================================
        doc_ref = (
            db.collection("notifications")
            .document(notification_id)
        )

        doc = doc_ref.get()

        # =================================================
        # KHÔNG TÌM THẤY
        # =================================================
        if not doc.exists:
            return {
                "success": False,
                "message": "Không tìm thấy thông báo"
            }

        data = doc.to_dict() or {}

        # =================================================
        # THÔNG BÁO ALL
        # =================================================
        if str(data.get("userId")) == "ALL":

            read_by = data.get(
                "readByUsers",
                []
            )

            if not isinstance(read_by, list):
                read_by = []

            read_by = [
                str(uid)
                for uid in read_by
            ]

            # Chưa đọc
            if str_user_id not in read_by:
                read_by.append(str_user_id)

                doc_ref.update({
                    "readByUsers": read_by
                })

            # Đã đọc rồi cũng SUCCESS
            return {
                "success": True,
                "id": notification_id,
                "isRead": True
            }

        # =================================================
        # THÔNG BÁO CÁ NHÂN
        # =================================================
        notification_user_id = str(
            data.get("userId")
        )

        # Không thuộc user hiện tại
        if notification_user_id != str_user_id:
            return {
                "success": False,
                "message": (
                    "Bạn không có quyền đọc thông báo này"
                )
            }

        # Đã đọc rồi → vẫn SUCCESS
        if data.get("isRead") is True:
            return {
                "success": True,
                "id": notification_id,
                "isRead": True
            }

        # Chưa đọc → đánh dấu đọc
        doc_ref.update({
            "isRead": True
        })

        return {
            "success": True,
            "id": notification_id,
            "isRead": True
        }