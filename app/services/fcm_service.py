import logging
from typing import Optional, Dict, Any, List
from firebase_admin import messaging
from app.configs.firebase import db

logger = logging.getLogger(__name__)


class FCMService:
    """
    Firebase Cloud Messaging (FCM) Service:
    - Gửi Push Notification tới thiết bị người dùng qua FCM Token hoặc Topic.
    - Quản lý token thiết bị trong Firestore collection `user_fcm_tokens`.
    - Tích hợp fallback an toàn (nếu user chưa đăng ký token FCM thì vẫn ghi thông báo in-app).
    """

    @classmethod
    def register_device_token(cls, user_id: str | int, fcm_token: str, device_type: str = "mobile"):
        """Lưu hoặc cập nhật FCM Device Token của User vào Firestore."""
        if not user_id or not fcm_token:
            return False
        str_user_id = str(user_id)
        try:
            token_doc_ref = db.collection("user_fcm_tokens").document(f"{str_user_id}_{fcm_token[-16:]}")
            token_doc_ref.set({
                "userId": str_user_id,
                "fcmToken": fcm_token,
                "deviceType": device_type,
                "updatedAt": firestore_server_timestamp()
            }, merge=True)
            logger.info(f"[FCM] Đã đăng ký device token cho user {str_user_id}")
            return True
        except Exception as e:
            logger.warning(f"[FCM] Không thể lưu device token cho user {str_user_id}: {e}")
            return False

    @classmethod
    def get_user_tokens(cls, user_id: str | int) -> List[str]:
        """Lấy tất cả FCM tokens của một User."""
        str_user_id = str(user_id)
        tokens = []
        try:
            docs = db.collection("user_fcm_tokens").where("userId", "==", str_user_id).stream()
            for doc in docs:
                t = doc.to_dict().get("fcmToken")
                if t:
                    tokens.append(t)
        except Exception as e:
            logger.warning(f"[FCM] Lỗi lấy token của user {str_user_id}: {e}")
        return tokens

    @classmethod
    def send_push_to_user(
        cls,
        user_id: str | int,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Gửi Push Notification tới tất cả thiết bị của một User qua FCM.
        Trả về số lượng thiết bị nhận thành công.
        """
        str_user_id = str(user_id)
        tokens = cls.get_user_tokens(str_user_id)
        payload_data = {k: str(v) for k, v in (data or {}).items()}

        if not tokens:
            # Nếu chưa có FCM token, thử gửi theo topic user_{user_id} (nếu client subscribe)
            try:
                topic = f"user_{str_user_id}"
                msg = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=payload_data,
                    topic=topic
                )
                messaging.send(msg)
                logger.info(f"[FCM] Gửi thành công push notification theo topic {topic}")
                return 1
            except Exception:
                return 0

        success_count = 0
        for token in tokens:
            try:
                msg = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=payload_data,
                    token=token,
                    android=messaging.AndroidConfig(priority="high"),
                    apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")))
                )
                messaging.send(msg)
                success_count += 1
            except Exception as e:
                logger.warning(f"[FCM] Không thể gửi push tới token {token[:10]}...: {e}")

        logger.info(f"[FCM] Đã gửi {success_count}/{len(tokens)} push notifications tới user {str_user_id}")
        return success_count


def firestore_server_timestamp():
    from firebase_admin import firestore
    return firestore.SERVER_TIMESTAMP
