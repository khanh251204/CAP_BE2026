from datetime import datetime, timezone
from firebase_admin import firestore
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

            # User này đã xóa thông báo chung -> ẩn đi
            deleted_by = data.get("deletedByUsers") or []
            if isinstance(deleted_by, list) and str_user_id in [
                str(uid) for uid in deleted_by
            ]:
                continue

            data.pop("deletedByUsers", None)
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
                "message": "Bạn không có quyền đọc thông báo này"
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
    # =====================================================
    # DELETE ONE (theo user)
    # =====================================================
    @staticmethod
    def delete_for_user(
        notification_id: str,
        user_id: str
    ):
        str_user_id = str(user_id)

        doc_ref = (
            db.collection("notifications")
            .document(notification_id)
        )

        doc = doc_ref.get()

        if not doc.exists:
            return {
                "success": False,
                "code": "NOT_FOUND",
                "message": "Không tìm thấy thông báo"
            }

        data = doc.to_dict() or {}
        owner = str(data.get("userId"))

        # Thông báo chung: không xóa cứng, chỉ ẩn với user này
        if owner == "ALL":
            doc_ref.update({
                "deletedByUsers": firestore.ArrayUnion([str_user_id])
            })
            return {
                "success": True,
                "id": notification_id
            }

        # Thông báo cá nhân: chỉ chủ sở hữu được xóa
        if owner != str_user_id:
            return {
                "success": False,
                "code": "FORBIDDEN",
                "message": "Bạn không có quyền xóa thông báo này"
            }

        doc_ref.delete()

        return {
            "success": True,
            "id": notification_id
        }

    # =====================================================
    # DELETE ALL (theo user)
    # =====================================================
    @staticmethod
    def delete_all_for_user(user_id: str):
        str_user_id = str(user_id)
        collection = db.collection("notifications")

        batch = db.batch()
        pending = 0
        deleted_count = 0

        def flush():
            nonlocal batch, pending
            if pending:
                batch.commit()
                batch = db.batch()
                pending = 0

        # Thông báo cá nhân -> xóa cứng
        for doc in collection.where("userId", "==", str_user_id).stream():
            batch.delete(doc.reference)
            pending += 1
            deleted_count += 1
            if pending >= 400:
                flush()

        # Thông báo chung -> ẩn với user này
        for doc in collection.where("userId", "==", "ALL").stream():
            deleted_by = (doc.to_dict() or {}).get("deletedByUsers") or []
            if str_user_id in [str(uid) for uid in deleted_by]:
                continue
            batch.update(doc.reference, {
                "deletedByUsers": firestore.ArrayUnion([str_user_id])
            })
            pending += 1
            deleted_count += 1
            if pending >= 400:
                flush()

        flush()

        return {
            "success": True,
            "deletedCount": deleted_count
        }
