"""
Groq client có dự phòng nhiều API key (failover).

Đọc key theo thứ tự ưu tiên: GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3...
Mỗi lần gọi luôn thử key chính trước; nếu key đó lỗi do hết hạn mức (429),
key sai/bị khóa (401/403), lỗi server Groq (5xx), mất kết nối hoặc timeout
thì tự chuyển sang key kế tiếp.

Lỗi do chính request (400, 404, 413, 422 — ví dụ file âm thanh hỏng, prompt sai)
không đổi key, vì key nào cũng sẽ lỗi như nhau.

Key vừa lỗi được tạm bỏ qua để các request sau không phải chờ key hỏng trước
rồi mới sang key dự phòng. Thời gian bỏ qua lấy theo Groq báo (header retry-after
hoặc "try again in 14m58s" khi hết hạn mức ngày), tối thiểu COOLDOWN_SECONDS.

Pool đọc từ .env tự nạp lại danh sách key khi file .env thay đổi
(thêm GROQ_API_KEY_3... không cần khởi động lại server).
"""
import logging
import os
import re
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

# Thời gian tạm bỏ qua một key sau khi nó lỗi (tối thiểu)
COOLDOWN_SECONDS = 60
# Không bỏ qua một key quá 1 ngày dù Groq báo lâu hơn
MAX_COOLDOWN_SECONDS = 24 * 3600

# BE/.env (file này nằm ở BE/app/ai/llm/)
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env")
_ENV_PATH = os.path.normpath(_ENV_PATH)
_RETRY_IN = re.compile(r"try again in\s+((?:\d+(?:\.\d+)?[hms]){1,3})", re.IGNORECASE)
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)([hms])")

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


def _retry_after_seconds(error: Exception) -> float:
    """Groq cho biết bao lâu nữa key dùng lại được; không rõ thì dùng COOLDOWN_SECONDS."""
    seconds = 0.0
    response = getattr(error, "response", None)
    header = response.headers.get("retry-after") if response is not None else None
    try:
        seconds = float(header) if header else 0.0
    except ValueError:
        seconds = 0.0
    match = _RETRY_IN.search(str(error))
    if match:
        unit = {"h": 3600, "m": 60, "s": 1}
        parsed = sum(float(n) * unit[u] for n, u in _DURATION_PART.findall(match.group(1)))
        seconds = max(seconds, parsed)
    return min(max(seconds, COOLDOWN_SECONDS), MAX_COOLDOWN_SECONDS)


def is_rate_limit_error(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    text = str(error)
    return status == 429 or "429" in text or "rate_limit" in text.lower()


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
        # Chỉ pool đọc từ .env mới tự nạp lại key; pool truyền key sẵn giữ nguyên
        self._from_env = api_keys is None
        self._env_mtime = self._read_env_mtime()
        keys = api_keys if api_keys is not None else get_groq_api_keys()
        if not keys:
            raise ValueError("GROQ_API_KEY chưa được cấu hình trong .env")

        self._lock = threading.Lock()
        self._keys: List[str] = []
        self._clients: list = []
        self._cooldown_until: List[float] = []
        self._set_keys(keys)
        logger.info(f"[Groq] Đã nạp {len(keys)} API key")

    @property
    def key_count(self) -> int:
        return len(self._clients)

    @staticmethod
    def _read_env_mtime() -> float:
        try:
            return os.path.getmtime(_ENV_PATH)
        except OSError:
            return 0.0

    def _set_keys(self, keys: List[str]) -> None:
        """Dựng lại client; key cũ còn trong danh sách giữ nguyên trạng thái cooldown."""
        # Khi có key dự phòng, SDK chỉ retry 1 lần để chuyển key nhanh hơn
        max_retries = 1 if len(keys) > 1 else 2
        old = dict(zip(self._keys, zip(self._clients, self._cooldown_until)))
        clients, cooldowns = [], []
        for k in keys:
            client, until = old.get(k, (None, 0.0))
            clients.append(client or Groq(api_key=k, max_retries=max_retries))
            cooldowns.append(until)
        self._keys, self._clients, self._cooldown_until = list(keys), clients, cooldowns

    def _reload_if_env_changed(self) -> None:
        """Thêm / đổi key trong .env thì tự nạp lại, không cần khởi động lại server."""
        if not self._from_env:
            return
        mtime = self._read_env_mtime()
        if mtime == self._env_mtime:
            return
        load_dotenv(_ENV_PATH, override=True)
        keys = get_groq_api_keys()
        with self._lock:
            self._env_mtime = mtime
            if keys and keys != self._keys:
                self._set_keys(keys)
                logger.info(f"[Groq] .env thay đổi, đã nạp lại {len(keys)} API key")

    def seconds_until_available(self) -> float:
        """Bao lâu nữa có ít nhất một key dùng lại được (0 nếu đang có key sẵn sàng)."""
        now = time.monotonic()
        with self._lock:
            if not self._cooldown_until:
                return 0.0
            return max(0.0, min(self._cooldown_until) - now)

    def _ordered_indexes(self) -> List[int]:
        """Key đang khỏe đứng trước (theo thứ tự ưu tiên), key đang cooldown xếp sau."""
        now = time.monotonic()
        with self._lock:
            ready = [i for i, t in enumerate(self._cooldown_until) if t <= now]
            cooling = [i for i, t in enumerate(self._cooldown_until) if t > now]
        return ready + cooling

    def _mark_failed(self, index: int, seconds: float = COOLDOWN_SECONDS) -> None:
        with self._lock:
            self._cooldown_until[index] = time.monotonic() + seconds

    def _mark_ok(self, index: int) -> None:
        with self._lock:
            self._cooldown_until[index] = 0.0

    def call(self, fn: Callable[[Groq], T]) -> T:
        """
        Chạy `fn(client)` với key ưu tiên; lỗi phía key/Groq thì thử key kế tiếp.
        Ví dụ: pool.call(lambda c: c.chat.completions.create(...))
        """
        self._reload_if_env_changed()
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
                cooldown = _retry_after_seconds(error)
                self._mark_failed(index, cooldown)
                status = getattr(error, "status_code", type(error).__name__)
                if attempt + 1 < len(order):
                    logger.warning(
                        f"[Groq] Key #{index + 1} lỗi ({status}), tạm nghỉ {int(cooldown)}s, "
                        f"chuyển sang key #{order[attempt + 1] + 1}/{len(order)}"
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
