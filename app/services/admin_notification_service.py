import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.configs.firebase import db
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

COLLECTION = "notifications"
EDITABLE_FIELDS = (
    "title",
    "description",
    "notificationType",
    "icon",
    "iconColor",
    "borderColor",
)
MAX_BATCH_SIZE = 400


def _to_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(doc_id: str, data: dict) -> Dict[str, Any]:
    is_global = str(data.get("userId")) == "ALL"
    read_by = data.get("readByUsers") or []
    deleted_by = data.get("deletedByUsers") or []

    return {
        "id": doc_id,
        "userId": str(data.get("userId", "")),
        "isGlobal": is_global,
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "notificationType": data.get("notificationType", "SYSTEM"),
        "icon": data.get("icon"),
        "iconColor": data.get("iconColor"),
        "borderColor": data.get("borderColor"),
        "createdAt": data.get("createdAt"),
        "updatedAt": data.get("updatedAt"),
        # Cá nhân: đã đọc hay chưa. Chung: số user đã đọc / đã ẩn.
        "isRead": bool(data.get("isRead", False)) if not is_global else None,
        "readCount": len(read_by) if is_global else (1 if data.get("isRead") else 0),
        "hiddenCount": len(deleted_by) if is_global else 0,
    }


def _get_doc_or_404(notification_id: str):
    doc_ref = db.collection(COLLECTION).document(notification_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông báo"
        )
    return doc_ref, doc


class AdminNotificationService:

    # =====================================================
    # LIST
    # =====================================================
    @staticmethod
    def list_notifications(
        page: int = 1,
        limit: int = 20,
        user_id: Optional[str] = None,
        notification_type: Optional[str] = None,
        scope: Optional[str] = None,
        search: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        # Chỉ dùng 1 điều kiện where trên Firestore để khỏi cần composite index,
        # phần lọc còn lại làm trong Python (thông báo tự xóa sau 14 ngày nên số lượng nhỏ).
        query = db.collection(COLLECTION)
        if user_id:
            query = query.where("userId", "==", str(user_id).strip())
        elif scope and scope.upper() == "GLOBAL":
            query = query.where("userId", "==", "ALL")

        from_date = _to_utc(from_date)
        to_date = _to_utc(to_date)
        keyword = search.strip().lower() if search else None
        type_filter = notification_type.strip().lower() if notification_type else None
        personal_only = bool(scope and scope.upper() == "PERSONAL")

        items: List[Dict[str, Any]] = []
        for doc in query.stream():
            data = doc.to_dict() or {}

            if personal_only and str(data.get("userId")) == "ALL":
                continue
            if type_filter and str(data.get("notificationType", "")).lower() != type_filter:
                continue
            if keyword:
                text = f"{data.get('title', '')} {data.get('description', '')}".lower()
                if keyword not in text:
                    continue

            created_at = _to_utc(data.get("createdAt"))
            if from_date and (not created_at or created_at < from_date):
                continue
            if to_date and (not created_at or created_at > to_date):
                continue

            items.append(_serialize(doc.id, data))

        items.sort(
            key=lambda x: _to_utc(x.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        total = len(items)
        start = (page - 1) * limit

        return {
            "items": items[start:start + limit],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": math.ceil(total / limit) if total else 0,
            }
        }

    # =====================================================
    # STATS
    # =====================================================
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        total = personal = global_count = personal_unread = 0
        by_type: Dict[str, int] = {}

        for doc in db.collection(COLLECTION).stream():
            data = doc.to_dict() or {}
            total += 1
            if str(data.get("userId")) == "ALL":
                global_count += 1
            else:
                personal += 1
                if not data.get("isRead"):
                    personal_unread += 1

            n_type = str(data.get("notificationType") or "SYSTEM")
            by_type[n_type] = by_type.get(n_type, 0) + 1

        return {
            "total": total,
            "personal": personal,
            "global": global_count,
            "personalUnread": personal_unread,
            "byType": by_type,
        }

    # =====================================================
    # DETAIL
    # =====================================================
    @staticmethod
    def get_notification(notification_id: str) -> Dict[str, Any]:
        _, doc = _get_doc_or_404(notification_id)
        data = doc.to_dict() or {}
        result = _serialize(doc.id, data)

        if result["isGlobal"]:
            result["readByUsers"] = [str(u) for u in data.get("readByUsers") or []]
            result["hiddenByUsers"] = [str(u) for u in data.get("deletedByUsers") or []]

        return result

    # =====================================================
    # SEND (1 user / nhiều user / tất cả)
    # =====================================================
    @staticmethod
    def send_notification(data: Dict[str, Any], admin_id: Optional[int] = None) -> Dict[str, Any]:
        user_ids = [str(u).strip() for u in (data.get("userIds") or []) if str(u).strip()]
        single = str(data.get("userId") or "").strip()

        if not user_ids:
            user_ids = [single] if single else ["ALL"]

        # Có "ALL" thì chỉ gửi 1 bản chung, không gửi trùng
        if any(u.upper() == "ALL" for u in user_ids):
            user_ids = ["ALL"]

        base = {k: data[k] for k in EDITABLE_FIELDS if data.get(k) is not None}

        created = []
        for uid in dict.fromkeys(user_ids):
            notif = NotificationService.create_notification({**base, "userId": uid})
            created.append(_serialize(notif["id"], notif))

        logger.info(f"[AdminNotification] admin={admin_id} sent {len(created)} notification(s) to {user_ids}")

        return {
            "success": True,
            "sentCount": len(created),
            "items": created,
        }

    # =====================================================
    # UPDATE
    # =====================================================
    @staticmethod
    def update_notification(notification_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        doc_ref, _ = _get_doc_or_404(notification_id)

        changes = {k: data[k] for k in EDITABLE_FIELDS if data.get(k) is not None}
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không có trường nào để cập nhật"
            )

        changes["updatedAt"] = datetime.now(timezone.utc)
        doc_ref.update(changes)

        return AdminNotificationService.get_notification(notification_id)

    # =====================================================
    # DELETE (xóa cứng, mọi user đều mất thông báo này)
    # =====================================================
    @staticmethod
    def delete_notification(notification_id: str) -> Dict[str, Any]:
        doc_ref, _ = _get_doc_or_404(notification_id)
        doc_ref.delete()
        return {"success": True, "id": notification_id}

    @staticmethod
    def bulk_delete(ids: List[str]) -> Dict[str, Any]:
        collection = db.collection(COLLECTION)
        batch = db.batch()
        pending = 0
        deleted: List[str] = []
        not_found: List[str] = []

        for notification_id in dict.fromkeys(i.strip() for i in ids if i and i.strip()):
            doc_ref = collection.document(notification_id)
            if not doc_ref.get().exists:
                not_found.append(notification_id)
                continue

            batch.delete(doc_ref)
            deleted.append(notification_id)
            pending += 1
            if pending >= MAX_BATCH_SIZE:
                batch.commit()
                batch = db.batch()
                pending = 0

        if pending:
            batch.commit()

        return {
            "success": True,
            "deletedCount": len(deleted),
            "deletedIds": deleted,
            "notFoundIds": not_found,
        }
