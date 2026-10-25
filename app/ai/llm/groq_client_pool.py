"""
Groq client có dự phòng nhiều API key (failover).

Đọc key theo thứ tự ưu tiên: GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3...
Mỗi lần gọi luôn thử key chính trước; nếu key đó lỗi do hết hạn mức (429),
key sai/bị khóa (401/403), lỗi server Groq (5xx), mất kết nối hoặc timeout
thì tự chuyển sang key kế tiếp.

Lỗi do chính request (400, 404, 413, 422 — ví dụ file âm thanh hỏng, prompt sai)
không đổi key, vì key nào cũng sẽ lỗi như nhau.

Key vừa lỗi được tạm bỏ qua trong COOLDOWN_SECONDS để các request sau
không phải chờ key hỏng trước rồi mới sang key dự phòng.
"""
import logging
import os
import threading
import time
from typing import Callable, List, Optional, TypeVar

from dotenv import load_dotenv
from groq import (
    APIConnectionError,
    APIStatusError,
    Groq,
)

load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Thời gian tạm bỏ qua một key sau khi nó lỗi
COOLDOWN_SECONDS = 60

# Mã HTTP được coi là lỗi của key / phía Groq -> chuyển sang key khác
_FAILOVER_STATUS = {401, 403, 429}


def get_groq_api_keys() -> List[str]:
    """Danh sách key theo thứ tự ưu tiên, bỏ trống và trùng lặp."""
    names = ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 10)]
    keys: List[str] = []
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def _should_failover(error: Exception) -> bool:
    # APITimeoutError là lớp con của APIConnectionError
    if isinstance(error, APIConnectionError):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code in _FAILOVER_STATUS or error.status_code >= 500
    return False


class GroqFailoverClient:
    """Bọc nhiều Groq client; gọi qua `call()` để tự chuyển key khi lỗi."""

    def __init__(self, api_keys: Optional[List[str]] = None):
        keys = api_keys if api_keys is not None else get_groq_api_keys()
        if not keys:
            raise ValueError("GROQ_API_KEY chưa được cấu hình trong .env")

        # Khi có key dự phòng, SDK chỉ retry 1 lần để chuyển key nhanh hơn
        max_retries = 1 if len(keys) > 1 else 2
        self._clients = [Groq(api_key=k, max_retries=max_retries) for k in keys]
        self._cooldown_until = [0.0] * len(keys)
        self._lock = threading.Lock()

    @property
    def key_count(self) -> int:
        return len(self._clients)

    def _ordered_indexes(self) -> List[int]:
        """Key đang khỏe đứng trước (theo thứ tự ưu tiên), key đang cooldown xếp sau."""
        now = time.monotonic()
        with self._lock:
            ready = [i for i, t in enumerate(self._cooldown_until) if t <= now]
            cooling = [i for i, t in enumerate(self._cooldown_until) if t > now]
        return ready + cooling

    def _mark_failed(self, index: int) -> None:
        with self._lock:
            self._cooldown_until[index] = time.monotonic() + COOLDOWN_SECONDS

    def _mark_ok(self, index: int) -> None:
        with self._lock:
            self._cooldown_until[index] = 0.0

    def call(self, fn: Callable[[Groq], T]) -> T:
        """
        Chạy `fn(client)` với key ưu tiên; lỗi phía key/Groq thì thử key kế tiếp.
        Ví dụ: pool.call(lambda c: c.chat.completions.create(...))
        """
        last_error: Optional[Exception] = None
        order = self._ordered_indexes()

        for attempt, index in enumerate(order):
            try:
                result = fn(self._clients[index])
                self._mark_ok(index)
                if attempt > 0:
                    logger.info(f"[Groq] Gọi thành công bằng key dự phòng #{index + 1}")
                return result
            except Exception as error:
                if not _should_failover(error):
                    raise
                last_error = error
                self._mark_failed(index)
                status = getattr(error, "status_code", type(error).__name__)
                if attempt + 1 < len(order):
                    logger.warning(
                        f"[Groq] Key #{index + 1} lỗi ({status}), chuyển sang key #{order[attempt + 1] + 1}"
                    )
                else:
                    logger.error(f"[Groq] Key #{index + 1} lỗi ({status}), đã hết key dự phòng")

        raise last_error  # type: ignore[misc]


_shared_pool: Optional[GroqFailoverClient] = None
_shared_lock = threading.Lock()


def get_groq_pool() -> GroqFailoverClient:
    """Pool dùng chung cho toàn ứng dụng (STT + LLM) để chia sẻ trạng thái cooldown."""
    global _shared_pool
    if _shared_pool is None:
        with _shared_lock:
            if _shared_pool is None:
                _shared_pool = GroqFailoverClient()
    return _shared_pool
