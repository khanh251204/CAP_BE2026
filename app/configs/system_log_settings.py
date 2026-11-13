"""
Cài đặt ghi system log THEO CHỨC NĂNG (bảng system_logs).

Hiện chỉ ghi log cho API mobile; API admin (/api/v1/admin/...) tạm thời KHÔNG ghi (mức OFF).
Mỗi chức năng có một mức:
- ALL     : ghi mọi request (thành công, lỗi người dùng 4xx, lỗi hệ thống 5xx)
- WARNING : chỉ ghi lỗi 4xx và 5xx (bỏ request thành công -> đỡ phình DB)
- ERROR   : chỉ ghi lỗi hệ thống 5xx
- OFF     : không ghi

Admin chỉnh trên trang System Logs > tab "Cài đặt ghi log" (API /admin/system-logs/settings), lưu vào file
runtime/system_log_settings.json. Hoặc đổi mặc định không cần sửa code: đặt biến môi trường SYSTEM_LOG_FEATURES, các cặp chuc_nang=MUC cách nhau dấu phẩy,
ghi đè lên mặc định bên dưới (khởi động lại server để áp dụng). Ví dụ:

    SYSTEM_LOG_FEATURES=report=ERROR,notification=WARNING,inventory=OFF

Áp dụng cho cả log request (SystemLogMiddleware) lẫn log sự kiện (log_event ở STT / LLM / AUTH / giao dịch):
log_event trong một request thuộc chức năng của request đó; ngoài request thì suy từ api_path hoặc step.
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"

LEVELS = ("ALL", "WARNING", "ERROR", "OFF")
# Mức tối thiểu của bản ghi (INFO / WARNING / ERROR) để được ghi, theo từng mức cài đặt
_MIN_RANK = {"ALL": 0, "WARNING": 1, "ERROR": 2, "OFF": 99}
_RECORD_RANK = {"INFO": 0, "DEBUG": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 2}

# (mã chức năng, tên hiển thị, các tiền tố đường dẫn sau /api/v1). Tiền tố dài / cụ thể đặt trước.
FEATURES: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("admin", "Quản trị (admin)", ("/admin",)),
    ("notification", "Thông báo", ("/notifications", "/users/me/devices")),
    ("auth", "Đăng nhập & tài khoản", ("/auth", "/users/me")),
    ("stt", "Giọng nói (STT)", ("/speech",)),
    ("agent", "Trợ lý AI (phân tích câu nói)", ("/agent",)),
    ("transaction", "Giao dịch", ("/transactions", "/sales", "/purchases")),
    ("product", "Sản phẩm", ("/products",)),
    ("inventory", "Kho", ("/inventory",)),
    ("customer", "Khách hàng", ("/customers",)),
    ("supplier", "Nhà cung cấp", ("/suppliers",)),
    ("debt", "Công nợ", ("/debts",)),
    ("report", "Báo cáo", ("/reports",)),
    ("closing", "Chốt sổ", ("/closing-periods", "/closing-reports", "/closing-settings")),
    ("other", "Khác", ()),
]
FEATURE_LABELS: Dict[str, str] = {code: label for code, label, _ in FEATURES}

# Mặc định: mọi chức năng mobile ghi đầy đủ như trước, admin tạm thời không ghi
DEFAULT_LEVELS: Dict[str, str] = {code: "ALL" for code, _, _ in FEATURES}
DEFAULT_LEVELS["admin"] = "OFF"

# log_event không có đường dẫn (vd giải mã token) -> chức năng theo bước kỹ thuật
_STEP_FEATURE = {"STT": "stt", "LLM": "agent", "AUTH": "auth", "ADMIN": "admin"}


def parse_levels(raw: Optional[str]) -> Dict[str, str]:
    """'report=ERROR,admin=OFF' -> {'report': 'ERROR', 'admin': 'OFF'}. Cặp sai thì bỏ qua (có cảnh báo)."""
    out: Dict[str, str] = {}
    for part in (raw or "").split(","):
        if not part.strip():
            continue
        code, _, level = part.partition("=")
        code, level = code.strip().lower(), level.strip().upper()
        if code not in FEATURE_LABELS or level not in LEVELS:
            logger.warning("[system_log_settings] Bỏ qua cài đặt không hợp lệ: %r", part.strip())
            continue
        out[code] = level
    return out


# ---------------------------------------------------------------------------
# Lưu cài đặt do admin chỉnh trên giao diện: file JSON phía server (không dùng DB).
# Ưu tiên: mặc định < biến môi trường SYSTEM_LOG_FEATURES < file (admin lưu). Xoá file = về mặc định + env.
# Mỗi worker tự đọc lại file khi file đổi (kiểm tra tối đa 5 giây / lần) nên nhiều worker vẫn đồng bộ.
# ---------------------------------------------------------------------------
_BE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RELOAD_SECONDS = 5.0
_state: Dict[str, object] = {"levels": None, "file_levels": {}, "meta": {}, "mtime": None, "checked_at": 0.0}
_test_override: Optional[Dict[str, str]] = None


def settings_file() -> str:
    """Đường dẫn file cài đặt (đổi bằng SYSTEM_LOG_SETTINGS_FILE)."""
    return os.getenv("SYSTEM_LOG_SETTINGS_FILE") or os.path.join(_BE_ROOT, "runtime", "system_log_settings.json")


def _env_levels() -> Dict[str, str]:
    return parse_levels(os.getenv("SYSTEM_LOG_FEATURES"))


def _read_file(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}, {}
    except (OSError, ValueError) as e:
        logger.warning("[system_log_settings] Không đọc được %s: %s", path, e)
        return {}, {}
    raw = data.get("levels") if isinstance(data, dict) else None
    levels = {k: str(v).upper() for k, v in (raw or {}).items()
              if k in FEATURE_LABELS and str(v).upper() in LEVELS}
    meta = {"updated_at": data.get("updated_at"), "updated_by": data.get("updated_by")} if isinstance(data, dict) else {}
    return levels, meta


def _refresh(force: bool = False) -> None:
    now = time.monotonic()
    if not force and _state["levels"] is not None and now - float(_state["checked_at"]) < _RELOAD_SECONDS:
        return
    _state["checked_at"] = now
    path = settings_file()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    if not force and _state["levels"] is not None and mtime == _state["mtime"]:
        return
    file_levels, meta = _read_file(path) if mtime is not None else ({}, {})
    _state.update(levels={**DEFAULT_LEVELS, **_env_levels(), **file_levels},
                  file_levels=file_levels, meta=meta, mtime=mtime)


def get_levels() -> Dict[str, str]:
    """Mức hiện hành của mọi chức năng."""
    if _test_override is not None:
        return dict(_test_override)
    _refresh()
    return dict(_state["levels"])  # type: ignore[arg-type]


def describe() -> Dict[str, object]:
    """Toàn bộ cài đặt để hiển thị trên trang admin: mức hiện hành, mức mặc định, nguồn của từng chức năng."""
    _refresh(force=True)
    levels, env, file_levels = get_levels(), _env_levels(), _state["file_levels"]
    features = []
    for code, label, prefixes in FEATURES:
        source = "admin" if code in file_levels else "env" if code in env else "default"  # type: ignore[operator]
        features.append({
            "code": code, "label": label, "paths": [API_PREFIX + p for p in prefixes],
            "level": levels[code], "default_level": {**DEFAULT_LEVELS, **env}[code], "source": source,
        })
    meta = _state["meta"] or {}
    return {"features": features, "levels": list(LEVELS),
            "updated_at": meta.get("updated_at"), "updated_by": meta.get("updated_by")}  # type: ignore[union-attr]


def validate_patch(patch: Dict[str, str]) -> Dict[str, str]:
    """Kiểm tra mã chức năng / mức do admin gửi lên. Sai thì ValueError (không lưu gì)."""
    if not isinstance(patch, dict) or not patch:
        raise ValueError("Chưa có thay đổi nào")
    clean = {}
    for code, level in patch.items():
        if code not in FEATURE_LABELS:
            raise ValueError(f"Chức năng không tồn tại: {code}")
        lv = str(level).upper()
        if lv not in LEVELS:
            raise ValueError(f"Mức không hợp lệ cho {code}: {level} (chọn {', '.join(LEVELS)})")
        clean[code] = lv
    return clean


def save_levels(patch: Dict[str, str], updated_by: Optional[int] = None) -> Dict[str, object]:
    """Áp thay đổi của admin, ghi file (ghi tạm rồi đổi tên để không hỏng file khi đang ghi), làm mới ngay."""
    clean = validate_patch(patch)
    _refresh(force=True)
    file_levels = {**_state["file_levels"], **clean}  # type: ignore[dict-item]
    path = settings_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"levels": file_levels, "updated_at": datetime.now().isoformat(timespec="seconds"),
                   "updated_by": updated_by}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    _refresh(force=True)
    return describe()


def reset_levels() -> Dict[str, object]:
    """Xoá cài đặt admin đã lưu: về mặc định + biến môi trường."""
    try:
        os.remove(settings_file())
    except FileNotFoundError:
        pass
    _refresh(force=True)
    return describe()


def set_levels(levels: Optional[Dict[str, str]] = None) -> None:
    """Dùng trong test / script: ép mức (không đụng file). None = bỏ ép, dùng mặc định + env + file."""
    global _test_override
    if levels is None:
        _test_override = None
        _state["levels"] = None
        return
    base = {**DEFAULT_LEVELS, **_env_levels()}
    for code, level in levels.items():
        if code in FEATURE_LABELS and str(level).upper() in LEVELS:
            base[code] = str(level).upper()
    _test_override = base


def feature_for_path(path: Optional[str]) -> str:
    """Chức năng của một đường dẫn API. Không thuộc nhóm nào -> 'other'."""
    p = (path or "").rstrip("/").lower()
    if p.startswith(API_PREFIX):
        p = p[len(API_PREFIX):]
    for code, _, prefixes in FEATURES:
        if any(p == pre or p.startswith(pre + "/") for pre in prefixes):
            return code
    return "other"


def feature_for_step(step: Optional[str]) -> str:
    return _STEP_FEATURE.get(str(step or "").upper(), "other")


def level_of(feature: str) -> str:
    levels = get_levels()
    return levels.get(feature, levels.get("other", "ALL"))


def is_off(feature: str) -> bool:
    return level_of(feature) == "OFF"


def should_log(feature: str, record_level: str) -> bool:
    """Bản ghi mức record_level (INFO / WARNING / ERROR) của chức năng feature có được ghi không."""
    need = _MIN_RANK.get(level_of(feature), 0)
    return _RECORD_RANK.get(str(record_level or "INFO").upper(), 0) >= need
