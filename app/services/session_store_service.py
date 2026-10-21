import json
import logging
import os
from collections.abc import MutableMapping
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from app.configs.database import get_db_session
from app.configs.settings import settings
from app.models.user_pending_confirmation_model import UserPendingConfirmation

logger = logging.getLogger(__name__)

# Redis optional import
_redis_client = None
_redis_available = False

try:
    import redis
    redis_url = getattr(settings, "REDIS_URL", None) or os.getenv("REDIS_URL")
    if redis_url:
        _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        # Test connection quickly
        _redis_client.ping()
        _redis_available = True
        logger.info("[SessionStore] Kết nối Redis thành công: %s", redis_url)
except Exception as e:
    _redis_client = None
    _redis_available = False
    logger.info("[SessionStore] Không dùng Redis (%s). Sử dụng Database table làm session store fallback.", e)


class SessionStoreService:
    """
    Dịch vụ lưu trữ và quản lý phiên xác nhận AI phân tán (Multi-worker & Multi-replica safe).
    - Hỗ trợ lưu trữ payload xác nhận theo session_id hoặc user_id.
    - TTL mặc định = 600 giây (10 phút).
    - Ưu tiên lưu trữ trên Redis nếu cấu hình REDIS_URL.
    - Dự phòng tự động (Fallback) trên MySQL bảng User_Pending_Confirmation.
    - Hỗ trợ Memory Cache dự phòng cuối cùng cho test cases không có DB/Redis.
    """

    DEFAULT_TTL_SECONDS = 600
    REDIS_PREFIX = "pending_conf:"
    _memory_cache: dict[str, tuple[dict, datetime]] = {}

    @classmethod
    def _normalize_key(cls, session_key: Union[str, int]) -> str:
        return str(session_key).strip()

    @classmethod
    def _extract_user_id(cls, session_key: Union[str, int], user_id: Optional[int] = None) -> Optional[int]:
        if user_id is not None:
            return user_id
        key_str = str(session_key).strip()
        if key_str.isdigit():
            return int(key_str)
        return None

    @classmethod
    def save_confirmation(
        cls,
        session_key: Union[str, int],
        data: dict,
        user_id: Optional[int] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS
    ) -> bool:
        """
        Lưu trạng thái chờ xác nhận với TTL.
        """
        norm_key = cls._normalize_key(session_key)
        uid = cls._extract_user_id(session_key, user_id)
        intent = data.get("intent") if isinstance(data, dict) else None
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(seconds=ttl_seconds)

        # 1. Thử lưu vào Redis nếu có
        if _redis_available and _redis_client:
            try:
                serialized = json.dumps(data, ensure_ascii=False)
                _redis_client.setex(
                    f"{cls.REDIS_PREFIX}{norm_key}",
                    ttl_seconds,
                    serialized
                )
                return True
            except Exception as e:
                logger.warning("[SessionStore] Lỗi ghi Redis: %s. Chuyển sang fallback DB.", e)

        # 2. Fallback lưu vào Database
        try:
            serialized = json.dumps(data, ensure_ascii=False)
            with get_db_session() as db:
                record = db.query(UserPendingConfirmation).filter(
                    UserPendingConfirmation.session_key == norm_key
                ).first()

                if record:
                    record.intent = intent
                    record.payload_json = serialized
                    record.expires_at = expires_at
                    if uid is not None:
                        record.user_id = uid
                else:
                    record = UserPendingConfirmation(
                        session_key=norm_key,
                        user_id=uid,
                        intent=intent,
                        payload_json=serialized,
                        expires_at=expires_at
                    )
                    db.add(record)
                db.commit()
            return True
        except Exception as e:
            logger.warning("[SessionStore] Lỗi lưu DB session: %s. Chuyển sang in-memory cache dự phòng.", e)

        # 3. Fallback in-memory cache
        cls._memory_cache[norm_key] = (data, expires_at)
        return True

    @classmethod
    def get_confirmation(cls, session_key: Union[str, int]) -> Optional[dict]:
        """
        Lấy thông tin chờ xác nhận. Tự động loại bỏ nếu đã quá hạn TTL.
        """
        norm_key = cls._normalize_key(session_key)
        now_utc = datetime.now(timezone.utc)

        # 1. Thử lấy từ Redis
        if _redis_available and _redis_client:
            try:
                val = _redis_client.get(f"{cls.REDIS_PREFIX}{norm_key}")
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.warning("[SessionStore] Lỗi đọc Redis: %s. Chuyển sang fallback DB.", e)

        # 2. Thử lấy từ Database
        try:
            with get_db_session() as db:
                record = db.query(UserPendingConfirmation).filter(
                    UserPendingConfirmation.session_key == norm_key
                ).first()

                if record:
                    rec_exp = record.expires_at
                    if rec_exp.tzinfo is None:
                        rec_exp = rec_exp.replace(tzinfo=timezone.utc)
                    if rec_exp < now_utc:
                        # Đã hết hạn -> xóa bỏ
                        db.delete(record)
                        db.commit()
                        return None
                    return json.loads(record.payload_json)
        except Exception as e:
            logger.warning("[SessionStore] Lỗi đọc DB session: %s. Chuyển sang kiểm tra memory cache.", e)

        # 3. Kiểm tra In-memory cache
        cached = cls._memory_cache.get(norm_key)
        if cached:
            data, exp = cached
            if exp < now_utc:
                cls._memory_cache.pop(norm_key, None)
                return None
            return data

        return None

    @classmethod
    def update_confirmation(
        cls,
        session_key: Union[str, int],
        updates: dict,
        ttl_seconds: int = DEFAULT_TTL_SECONDS
    ) -> Optional[dict]:
        """
        Cập nhật bổ sung các field cho session đang chờ xác nhận (ví dụ: voice_id, input_method).
        """
        existing = cls.get_confirmation(session_key)
        if not existing:
            return None
        existing.update(updates)
        cls.save_confirmation(session_key, existing, ttl_seconds=ttl_seconds)
        return existing

    @classmethod
    def delete_confirmation(cls, session_key: Union[str, int]) -> bool:
        """
        Xóa phiên xác nhận sau khi hoàn thành hoặc bị hủy bỏ.
        """
        norm_key = cls._normalize_key(session_key)
        deleted = False

        if _redis_available and _redis_client:
            try:
                _redis_client.delete(f"{cls.REDIS_PREFIX}{norm_key}")
                deleted = True
            except Exception as e:
                logger.warning("[SessionStore] Lỗi xóa Redis: %s", e)

        try:
            with get_db_session() as db:
                record = db.query(UserPendingConfirmation).filter(
                    UserPendingConfirmation.session_key == norm_key
                ).first()
                if record:
                    db.delete(record)
                    db.commit()
                    deleted = True
        except Exception as e:
            logger.warning("[SessionStore] Lỗi xóa DB session: %s", e)

        if norm_key in cls._memory_cache:
            cls._memory_cache.pop(norm_key, None)
            deleted = True

        return deleted

    @classmethod
    def pop_confirmation(cls, session_key: Union[str, int], default: Any = None) -> Any:
        """
        Lấy ra và xóa ngay phiên xác nhận (tương tự dict.pop).
        """
        data = cls.get_confirmation(session_key)
        if data is not None:
            cls.delete_confirmation(session_key)
            return data
        return default

    @classmethod
    def cleanup_expired(cls) -> int:
        """
        Xóa dọn dẹp các session đã hết hạn trong database.
        """
        now_utc = datetime.now(timezone.utc)
        count = 0
        try:
            with get_db_session() as db:
                expired = db.query(UserPendingConfirmation).filter(
                    UserPendingConfirmation.expires_at < now_utc
                ).all()
                count = len(expired)
                for item in expired:
                    db.delete(item)
                if count > 0:
                    db.commit()
        except Exception as e:
            logger.warning("[SessionStore] Lỗi cleanup_expired: %s", e)
        return count


class PendingConfirmationsProxy(MutableMapping):
    """
    Dict-like Proxy tương thích 100% với biến toàn cục `pending_confirmations` trước đây,
    nhưng chuyển toàn bộ thao tác read/write xuống SessionStoreService (Redis / DB).
    """

    def __getitem__(self, key: Any) -> Any:
        val = SessionStoreService.get_confirmation(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        if not isinstance(value, dict):
            value = {"data": value}
        SessionStoreService.save_confirmation(key, value)

    def __delitem__(self, key: Any) -> None:
        deleted = SessionStoreService.delete_confirmation(key)
        if not deleted:
            raise KeyError(key)

    def __iter__(self):
        # Không khuyến khích iterate qua toàn bộ session store phân tán
        return iter([])

    def __len__(self) -> int:
        return 0

    def __contains__(self, key: Any) -> bool:
        return SessionStoreService.get_confirmation(key) is not None

    def get(self, key: Any, default: Any = None) -> Any:
        val = SessionStoreService.get_confirmation(key)
        return val if val is not None else default

    def pop(self, key: Any, default: Any = None) -> Any:
        return SessionStoreService.pop_confirmation(key, default)
