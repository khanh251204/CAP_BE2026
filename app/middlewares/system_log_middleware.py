import re
import json
import time
import uuid
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.background import BackgroundTask, BackgroundTasks

from app.configs.cookie import JWT_ACCESS_COOKIE_NAME
from app.configs.database import get_db_session
from app.configs.jwt import decode_access_token
from app.models.system_log_model import SystemLog, SystemLogLevel, SystemLogStep

logger = logging.getLogger(__name__)

# ContextVar lưu trữ request_id cho request hiện tại
current_request_id_var: ContextVar[Optional[str]] = ContextVar("current_request_id", default=None)


def get_current_request_id() -> Optional[str]:
    """Lấy request_id của request hiện tại từ ContextVar."""
    return current_request_id_var.get()


SENSITIVE_KEYS = {
    "password", "pass", "pwd", "token", "access_token", "refresh_token",
    "authorization", "secret", "cookie", "set-cookie", "credit_card",
    "audio", "file", "audio_base64", "content", "apikey"
}


def mask_sensitive_data(data: Any, max_depth: int = 5) -> Any:
    """
    Đệ quy che các thông tin nhạy cảm trong headers, params, body, detail.
    """
    if max_depth <= 0:
        return "[DEPTH_EXCEEDED]"

    if isinstance(data, dict):
        masked_dict = {}
        for key, val in data.items():
            lower_key = str(key).lower().strip()
            if any(sens in lower_key for sens in SENSITIVE_KEYS):
                masked_dict[key] = "***MASKED***"
            else:
                masked_dict[key] = mask_sensitive_data(val, max_depth - 1)
        return masked_dict

    elif isinstance(data, (list, tuple, set)):
        return [mask_sensitive_data(item, max_depth - 1) for item in data]

    elif isinstance(data, (str, bytes)):
        str_val = str(data)
        if str_val.startswith("Bearer ") or (len(str_val) > 80 and str_val.count(".") == 2):
            return "Bearer ***MASKED***"
        return str_val

    return data


EXCLUDED_PATHS = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico"
}


def _should_skip_logging(request: Request) -> bool:
    """
    Bỏ qua các đường dẫn hoặc method không cần ghi log để tránh làm phình DB
    và triệt tiêu tình trạng nghẽn connection pool.
    """
    # 1. Bỏ qua CORS preflight OPTIONS request hoàn toàn
    if request.method == "OPTIONS":
        return True

    # 2. Bỏ qua WebSocket connections
    if request.scope.get("type") == "websocket":
        return True

    path = request.url.path
    clean_path = path.rstrip("/")

    # 3. Bỏ qua tài liệu API và static
    if clean_path in EXCLUDED_PATHS or path in EXCLUDED_PATHS:
        return True

    # 4. Bỏ qua chính endpoint admin system-logs để tránh vòng lặp ghi log
    if "/admin/system-logs" in clean_path or "/admin/system_logs" in clean_path:
        return True

    # 5. Bỏ qua WebSocket route reports
    if "/reports/ws" in clean_path:
        return True

    # 6. Bỏ qua root và health checks
    if clean_path in ("", "/", "/health", "/ping"):
        return True

    return False


def _extract_user_id_safe(request: Request) -> Optional[int]:
    """Trích xuất user_id từ Cookie hoặc Header Authorization một cách an toàn."""
    try:
        token = request.cookies.get(JWT_ACCESS_COOKIE_NAME)
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
        if token:
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                return int(payload["sub"])
    except Exception:
        pass
    return None


def _parse_device_info(request: Request) -> Optional[Dict[str, Any]]:
    """Phân tích thông tin thiết bị từ X-Device hoặc User-Agent."""
    device_raw = request.headers.get("X-Device")
    if device_raw:
        try:
            parsed = json.loads(device_raw)
            if isinstance(parsed, dict):
                return mask_sensitive_data(parsed)
        except Exception:
            pass
        return {"raw": str(device_raw)[:100]}

    ua = request.headers.get("user-agent", "")
    if ua:
        ua_lower = ua.lower()
        platform = "other"
        os_version = None

        if "android" in ua_lower:
            platform = "android"
            m = re.search(r"android\s+([0-9.]+)", ua_lower)
            if m:
                os_version = m.group(1)
        elif "iphone" in ua_lower or "ipad" in ua_lower or "ios" in ua_lower:
            platform = "ios"
            m = re.search(r"os\s+([0-9_]+)", ua_lower)
            if m:
                os_version = m.group(1).replace("_", ".")
        elif "windows" in ua_lower:
            platform = "windows"
        elif "mac" in ua_lower:
            platform = "macos"
        elif "linux" in ua_lower:
            platform = "linux"

        return {
            "platform": platform,
            "os_version": os_version,
            "user_agent": ua[:200]
        }

    return None


def resolve_log_step(api_path: str = None, current_step: str = None) -> str:
    """Tự động phân loại bước kỹ thuật (step) dựa vào api_path nếu chưa được chỉ định."""
    if current_step and current_step != "OTHER":
        return current_step

    path = (api_path or "").lower()
    # 1. STT: CHỈ API /api/v1/stt/groq (hoặc /stt/groq)
    if "/stt/groq" in path or path.endswith("/stt"):
        return "STT"

    # 2. AI (NLP): phân tích ý định và bóc tách thực thể
    if any(k in path for k in ("/analyze", "/agent", "/chat", "/llm", "/ai", "/predict")):
        return "LLM"

    # 3. AUTH: xác thực người dùng
    if any(k in path for k in ("/login", "/register", "/auth", "/token", "/refresh", "/me", "/logout")):
        return "AUTH"

    # 4. ADMIN: các API quản trị admin
    if "/admin" in path:
        return "ADMIN"

    # 5. KHÁC (OTHER): toàn bộ các API còn lại
    return "OTHER"


def _write_log_to_db_sync(log_data: dict):
    """Ghi bản ghi SystemLog vào DB một cách an toàn và độc lập."""
    db = None
    try:
        from app.configs.database import get_db_session
        db = get_db_session()
        resolved_step = resolve_log_step(log_data.get("api_path"), log_data.get("step"))
        log_entry = SystemLog(
            created_at=log_data.get("created_at"),
            level=log_data.get("level", "INFO"),
            step=resolved_step,
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
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.warning(f"[SystemLogMiddleware] Failed to write log: {e}")
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


class SystemLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. Trích xuất hoặc sinh mới request_id
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token_ctx = current_request_id_var.set(req_id)
        request.state.request_id = req_id

        # Kiểm tra bỏ qua log nếu đường dẫn/method thuộc danh sách loại trừ
        if _should_skip_logging(request):
            try:
                response = await call_next(request)
                response.headers["X-Request-ID"] = req_id
                return response
            finally:
                current_request_id_var.reset(token_ctx)

        start_time = time.time()
        method = request.method
        app_version = request.headers.get("X-App-Version")
        device_info = _parse_device_info(request)

        # Trích xuất body an toàn nếu là json
        body_dict = None
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type and method in ("POST", "PUT", "PATCH"):
            try:
                raw_body = await request.body()
                if raw_body:
                    parsed_body = json.loads(raw_body)
                    body_dict = mask_sensitive_data(parsed_body)
            except Exception:
                pass

        status_code = 500
        error_detail = None
        exception_msg = None
        response: Optional[Response] = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = req_id
            return response

        except Exception as exc:
            import traceback
            status_code = 500
            exception_msg = str(exc)
            error_detail = {
                "error_type": type(exc).__name__,
                "error_message": exception_msg,
                "stack_trace": traceback.format_exc()[-1000:]
            }
            raise exc

        finally:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            user_id = _extract_user_id_safe(request)

            if status_code >= 500:
                level = SystemLogLevel.ERROR.value
                message = f"{method} {path} failed with status {status_code}"
                if exception_msg:
                    message += f": {exception_msg}"
            elif status_code >= 400:
                level = SystemLogLevel.WARNING.value
                message = f"{method} {path} returned client error {status_code}"
            else:
                level = SystemLogLevel.INFO.value
                message = f"{method} {path} executed successfully ({duration_ms}ms)"

            query_params_dict = dict(request.query_params)
            masked_query_params = mask_sensitive_data(query_params_dict)

            detail_payload = {
                "client_host": request.client.host if request.client else None,
                "query_params": masked_query_params,
            }
            if body_dict:
                detail_payload["body"] = body_dict
            if error_detail:
                detail_payload["error"] = error_detail

            log_dict = {
                "created_at": None,
                "level": level,
                "step": SystemLogStep.OTHER.value,
                "api_path": path[:255],
                "http_method": method[:10],
                "status_code": status_code,
                "duration_ms": duration_ms,
                "message": message[:500] if message else None,
                "detail": detail_payload,
                "request_id": req_id[:64],
                "user_id": user_id,
                "device": device_info,
                "app_version": str(app_version)[:50] if app_version else None,
            }

            if response is not None:
                if response.background:
                    if isinstance(response.background, BackgroundTasks):
                        response.background.add_task(_write_log_to_db_sync, log_dict)
                    else:
                        existing_task = response.background
                        bg = BackgroundTasks()
                        bg.add_task(existing_task)
                        bg.add_task(_write_log_to_db_sync, log_dict)
                        response.background = bg
                else:
                    response.background = BackgroundTask(_write_log_to_db_sync, log_dict)
            else:
                _write_log_to_db_sync(log_dict)

            current_request_id_var.reset(token_ctx)
