from datetime import datetime, timezone
from app.configs.firebase import db


class NotificationRepository:

    # =====================================================
    # GET ALL NOTIFICATIONS
    # =====================================================
    @staticmethod
    def get_all(user_id: str):
        str_user_id = str(user_id)

        # ThÃ´ng bÃ¡o cÃ¡ nhÃ¢n
        personal_docs = (
            db.collection("notifications")
            .where("userId", "==", str_user_id)
            .stream()
        )

        # ThÃ´ng bÃ¡o cho táº¥t cáº£
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

            # Äáº£m báº£o luÃ´n cÃ³ isRead
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

            # Notification cÃ¡ nhÃ¢n
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
        # Láº¤Y DOCUMENT
        # =================================================
        doc_ref = (
            db.collection("notifications")
            .document(notification_id)
        )

        doc = doc_ref.get()

        # =================================================
        # KHÃ”NG TÃŒM THáº¤Y
        # =================================================
        if not doc.exists:
            return {
                "success": False,
                "message": "KhÃ´ng tÃ¬m tháº¥y thÃ´ng bÃ¡o"
            }

        data = doc.to_dict() or {}

        # =================================================
        # THÃ”NG BÃO ALL
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

            # ChÆ°a Ä‘á»c
            if str_user_id not in read_by:
                read_by.append(str_user_id)

                doc_ref.update({
                    "readByUsers": read_by
                })

            # ÄÃ£ Ä‘á»c rá»“i cÅ©ng SUCCESS
            return {
                "success": True,
                "id": notification_id,
                "isRead": True
            }

        # =================================================
        # THÃ”NG BÃO CÃ NHÃ‚N
        # =================================================
        notification_user_id = str(
            data.get("userId")
        )

        # KhÃ´ng thuá»™c user hiá»‡n táº¡i
        if notification_user_id != str_user_id:
            return {
                "success": False,
                "message": "Báº¡n khÃ´ng cÃ³ quyá»n Ä‘á»c thÃ´ng bÃ¡o nÃ y"
            }

        # ÄÃ£ Ä‘á»c rá»“i â†’ váº«n SUCCESS
        if data.get("isRead") is True:
            return {
                "success": True,
                "id": notification_id,
                "isRead": True
            }

        # ChÆ°a Ä‘á»c â†’ Ä‘Ã¡nh dáº¥u Ä‘á»c
        doc_ref.update({
            "isRead": True
        })

        return {
            "success": True,
            "id": notification_id,
            "isRead": True
        }
