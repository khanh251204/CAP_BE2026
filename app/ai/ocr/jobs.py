"""
Hàng việc OCR chạy nền: POST trả job_id ngay, app hỏi lại kết quả (OCR mất vài giây đến vài phút tùy engine).

Lưu trong bộ nhớ của tiến trình API: đủ cho một tiến trình (uvicorn mặc định). Chạy nhiều worker thì
GET có thể rơi vào worker khác và báo không thấy việc -> khi đó cần chuyển sang Redis.
Mỗi việc gắn user_id; user khác hỏi thì coi như không tồn tại.
"""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

JOB_TTL_SECONDS = 30 * 60
# Vintern tự khóa 1 ảnh/lần; 2 luồng để việc dùng Gemini không phải xếp hàng sau Vintern
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")
_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _cleanup(now: float) -> None:
    for job_id in [k for k, v in _jobs.items() if now - v["created_at"] > JOB_TTL_SECONDS]:
        _jobs.pop(job_id, None)


def submit(user_id: int, fn: Callable[[], Dict[str, Any]]) -> str:
    """Chạy fn() ở luồng nền; fn trả kết quả cuối (dict) hoặc ném lỗi."""
    job_id = uuid.uuid4().hex
    now = time.time()
    with _lock:
        _cleanup(now)
        _jobs[job_id] = {"user_id": user_id, "created_at": now, "done": False, "result": None, "error": None}

    def run():
        try:
            result, error = fn(), None
        except Exception as e:  # noqa: BLE001 - lỗi được trả cho app khi hỏi lại
            result, error = None, e
        with _lock:
            job = _jobs.get(job_id)
            if job is not None:
                job.update(done=True, result=result, error=error, finished_at=time.time())

    _executor.submit(run)
    return job_id


def get(user_id: int, job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job["user_id"] != user_id:
            return None
        return dict(job)
