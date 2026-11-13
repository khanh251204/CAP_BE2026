"""
Cài đặt ghi system log THEO CHỨC NĂNG (bảng system_logs).

Hiện chỉ ghi log cho API mobile; API admin (/api/v1/admin/...) tạm thời KHÔNG ghi (mức OFF).
Mỗi chức năng có một mức:
- ALL     : ghi mọi request (thành công, lỗi người dùng 4xx, lỗi hệ thống 5xx)
- WARNING : chỉ ghi lỗi 4xx và 5xx (bỏ request thành công -> đỡ phình DB)
- ERROR   : chỉ ghi lỗi hệ thống 5xx
- OFF     : không ghi

Đổi mức không cần sửa code: đặt biến môi trường SYSTEM_LOG_FEATURES, các cặp chuc_nang=MUC cách nhau dấu phẩy,
ghi đè lên mặc định bên dưới (khởi động lại server để áp dụng). Ví dụ:

    SYSTEM_LOG_FEATURES=report=ERROR,notification=WARNING,inventory=OFF

Áp dụng cho cả log request (SystemLogMiddleware) lẫn log sự kiện (log_event ở STT / LLM / AUTH / giao dịch):
log_event trong một request thuộc chức năng của request đó; ngoài request thì suy từ api_path hoặc step.
"""
import logging
import os
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


_levels: Dict[str, str] = {**DEFAULT_LEVELS, **parse_levels(os.getenv("SYSTEM_LOG_FEATURES"))}


def get_levels() -> Dict[str, str]:
    """Mức hiện hành của mọi chức năng."""
    return dict(_levels)


def set_levels(levels: Optional[Dict[str, str]] = None) -> None:
    """Dùng trong test / script: đặt lại mức (None = mặc định + biến môi trường). Mã / mức sai bị bỏ qua."""
    global _levels
    base = {**DEFAULT_LEVELS, **parse_levels(os.getenv("SYSTEM_LOG_FEATURES"))}
    for code, level in (levels or {}).items():
        if code in FEATURE_LABELS and str(level).upper() in LEVELS:
            base[code] = str(level).upper()
    _levels = base


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
    return _levels.get(feature, _levels.get("other", "ALL"))


def is_off(feature: str) -> bool:
    return level_of(feature) == "OFF"


def should_log(feature: str, record_level: str) -> bool:
    """Bản ghi mức record_level (INFO / WARNING / ERROR) của chức năng feature có được ghi không."""
    need = _MIN_RANK.get(level_of(feature), 0)
    return _RECORD_RANK.get(str(record_level or "INFO").upper(), 0) >= need
