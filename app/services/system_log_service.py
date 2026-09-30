import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from app.configs.database import get_db_session
from app.models.system_log_model import SystemLog, SystemLogLevel, SystemLogStep
from app.middlewares.system_log_middleware import get_current_request_id, mask_sensitive_data

logger = logging.getLogger(__name__)


def log_event(
    level: str,
    step: str,
    message: str,
    detail: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    status_code: Optional[int] = None,
    api_path: Optional[str] = None,
    duration_ms: Optional[float] = None,
    device: Optional[Dict[str, Any]] = None,
    app_version: Optional[str] = None
):
    """
    Helper ghi nhận sự kiện/lỗi tại các bước then chốt trong hệ thống (STT, LLM, DB, AUTH).
    - Tự động lấy request_id từ ContextVar nếu không truyền.
    - Mask thông tin nhạy cảm trong detail.
    - Ghi bất đồng bộ, không làm crash luồng chính nếu DB gặp sự cố.
    """
    try:
        resolved_req_id = request_id or get_current_request_id()

        # Validate / normalize level
        normalized_level = level.upper() if level else "INFO"
        if normalized_level not in SystemLogLevel.__members__:
            normalized_level = "INFO"

        # Validate / normalize step
        normalized_step = step.upper() if step else "OTHER"
        if normalized_step not in SystemLogStep.__members__:
            normalized_step = "OTHER"

        masked_detail = mask_sensitive_data(detail) if detail is not None else None

        log_data = {
            "created_at": datetime.now(),
            "level": normalized_level,
            "step": normalized_step,
            "message": str(message)[:500] if message else None,
            "detail": masked_detail,
            "request_id": str(resolved_req_id)[:64] if resolved_req_id else None,
            "user_id": user_id,
            "status_code": status_code,
            "api_path": str(api_path)[:255] if api_path else None,
            "duration_ms": duration_ms,
            "device": mask_sensitive_data(device) if device else None,
            "app_version": str(app_version)[:50] if app_version else None
        }

        _persist_log_entry(log_data)
    except Exception as e:
        logger.warning(f"[SystemLogService] log_event error: {e}")


def _persist_log_entry(log_data: dict):
    """Ghi trực tiếp 1 bản ghi SystemLog vào DB session riêng."""
    db = None
    try:
        db = get_db_session()
        entry = SystemLog(
            created_at=log_data.get("created_at") or datetime.now(),
            level=log_data.get("level", "INFO"),
            step=log_data.get("step", "OTHER"),
            api_path=log_data.get("api_path"),
            http_method=log_data.get("http_method"),
            status_code=log_data.get("status_code"),
            duration_ms=log_data.get("duration_ms"),
            message=log_data.get("message"),
            detail=log_data.get("detail"),
            request_id=log_data.get("request_id"),
            user_id=log_data.get("user_id"),
            device=log_data.get("device"),
            app_version=log_data.get("app_version"),
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.warning(f"[SystemLogService] Failed to persist log entry: {e}")
        if db:
            try:
                db.rollback()
            except Exception:
                pass
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass
