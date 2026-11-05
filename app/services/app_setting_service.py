"""
Cài đặt ghi vết / log do admin chỉnh (bảng App_Setting, khoá "observability").

Mục tiêu: Audit Log và System Log ghi rất nhiều dòng nên admin phải chọn được chức năng nào cần ghi,
ghi chi tiết đến đâu và giữ bao lâu. Đọc qua cache ngắn (TTL) vì được gọi trên đường ghi dữ liệu:
mỗi lần ghi không được tốn thêm một truy vấn.
"""
import copy
import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

OBSERVABILITY_KEY = "observability"
CACHE_TTL_SECONDS = 30

AUDIT_ENTITIES = ("TRANSACTION", "TRANSACTION_DETAIL", "DEBT", "DEBT_PAYMENT", "INVENTORY")

DEFAULTS: Dict[str, Any] = {
    "audit": {
        # Chức năng nào được ghi vết. Kho mặc định tắt vì Inventory_Transaction vốn đã là sổ cái biến động kho.
        "enabled": {
            "TRANSACTION": True,
            "TRANSACTION_DETAIL": True,
            "DEBT": True,
            "DEBT_PAYMENT": True,
            "INVENTORY": False,
        },
        # Tắt: khi SỬA chỉ lưu các trường đổi (không lưu toàn bộ bản ghi trước / sau) -> nhẹ hơn nhiều
        "full_snapshots": True,
        # Số ngày giữ vết; 0 = giữ mãi
        "retention_days": 365,
    },
    "system_log": {
        # Tắt: chỉ ghi request lỗi (4xx / 5xx), bỏ request thành công (phần lớn dung lượng)
        "log_success_requests": True,
        # Tắt: không lưu body / query của request trong log
        "store_request_body": True,
        "retention_days": 30,
        "error_retention_days": 90,
    },
}

LIMITS = {
    ("audit", "retention_days"): (0, 3650),
    ("system_log", "retention_days"): (1, 3650),
    ("system_log", "error_retention_days"): (1, 3650),
}


class SettingError(ValueError):
    """Giá trị cài đặt không hợp lệ."""


def defaults() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULTS)


def _merge(base: Dict[str, Any], patch: Dict[str, Any], strict: bool) -> Dict[str, Any]:
    """Ghép patch vào base theo đúng cấu trúc mặc định; strict: sai khoá / sai kiểu thì báo lỗi, ngược lại bỏ qua."""
    out = copy.deepcopy(base)
    for section, values in (patch or {}).items():
        if section not in DEFAULTS:
            if strict:
                raise SettingError(f"Nhóm cài đặt không tồn tại: {section}")
            continue
        if not isinstance(values, dict):
            if strict:
                raise SettingError(f"Nhóm '{section}' phải là một đối tượng")
            continue
        for key, value in values.items():
            if key not in DEFAULTS[section]:
                if strict:
                    raise SettingError(f"Cài đặt không tồn tại: {section}.{key}")
                continue
            default = DEFAULTS[section][key]
            if isinstance(default, dict):  # audit.enabled
                if not isinstance(value, dict):
                    if strict:
                        raise SettingError(f"{section}.{key} phải là một đối tượng")
                    continue
                for sub, flag in value.items():
                    if sub not in default:
                        if strict:
                            raise SettingError(f"Chức năng không tồn tại: {sub}")
                        continue
                    if not isinstance(flag, bool):
                        if strict:
                            raise SettingError(f"{section}.{key}.{sub} phải là true / false")
                        continue
                    out[section][key][sub] = flag
            elif isinstance(default, bool):
                if not isinstance(value, bool):
                    if strict:
                        raise SettingError(f"{section}.{key} phải là true / false")
                    continue
                out[section][key] = value
            else:  # số nguyên có giới hạn
                if isinstance(value, bool) or not isinstance(value, int):
                    if strict:
                        raise SettingError(f"{section}.{key} phải là số nguyên")
                    continue
                low, high = LIMITS.get((section, key), (0, 3650))
                if not (low <= value <= high):
                    if strict:
                        raise SettingError(f"{section}.{key} phải từ {low} đến {high}")
                    continue
                out[section][key] = value
    return out


def normalize(stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Giá trị đọc từ DB -> đủ mọi khoá (thiếu thì mặc định, sai thì bỏ qua)."""
    return _merge(DEFAULTS, stored or {}, strict=False)


def validate_update(current: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Cài đặt mới sau khi áp patch của admin; sai thì ném SettingError."""
    return _merge(current, patch, strict=True)


# ---------------------------------------------------------------- cache

_lock = threading.Lock()
_cache: Dict[str, Any] = {"expires": 0.0, "value": None}
_override: Optional[Dict[str, Any]] = None


def _load_from_db() -> Dict[str, Any]:
    from app.configs.database import get_db_session
    from app.models.app_setting_model import AppSetting

    db = get_db_session()
    try:
        row = db.query(AppSetting).filter(AppSetting.setting_key == OBSERVABILITY_KEY).first()
        return normalize(row.value if row else None)
    finally:
        db.close()


def get_settings() -> Dict[str, Any]:
    """Cài đặt hiện hành (cache 30 giây; lỗi đọc DB thì dùng bản cũ / mặc định, không làm hỏng luồng chính)."""
    if _override is not None:
        return _override
    now = time.monotonic()
    with _lock:
        if _cache["value"] is not None and now < _cache["expires"]:
            return _cache["value"]
    try:
        value = _load_from_db()
    except Exception as exc:
        logger.warning("[Setting] không đọc được cài đặt, dùng bản cũ / mặc định: %s", exc)
        value = _cache["value"] or defaults()
    with _lock:
        _cache["value"] = value
        _cache["expires"] = now + CACHE_TTL_SECONDS
    return value


def invalidate_cache() -> None:
    with _lock:
        _cache["value"] = None
        _cache["expires"] = 0.0


def get_audit_settings() -> Dict[str, Any]:
    return get_settings()["audit"]


def get_system_log_settings() -> Dict[str, Any]:
    return get_settings()["system_log"]


def is_audit_enabled(entity_type: str) -> bool:
    return bool(get_audit_settings()["enabled"].get(entity_type, False))


def save_settings(db: Any, patch: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
    """Áp patch của admin, lưu DB, làm mới cache. Sai giá trị -> SettingError (không lưu gì)."""
    from app.models.app_setting_model import AppSetting

    row = db.query(AppSetting).filter(AppSetting.setting_key == OBSERVABILITY_KEY).first()
    current = normalize(row.value if row else None)
    new_value = validate_update(current, patch)
    if row:
        row.value = new_value
        row.updated_by = user_id
    else:
        db.add(AppSetting(setting_key=OBSERVABILITY_KEY, value=new_value, updated_by=user_id))
    db.commit()
    invalidate_cache()
    return new_value


def reset_settings(db: Any, user_id: Optional[int]) -> Dict[str, Any]:
    from app.models.app_setting_model import AppSetting

    value = defaults()
    row = db.query(AppSetting).filter(AppSetting.setting_key == OBSERVABILITY_KEY).first()
    if row:
        row.value = value
        row.updated_by = user_id
    else:
        db.add(AppSetting(setting_key=OBSERVABILITY_KEY, value=value, updated_by=user_id))
    db.commit()
    invalidate_cache()
    return value


@contextmanager
def override_settings(patch: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
    """Dùng trong test / script: ép cài đặt (không đụng DB). patch=None -> mặc định."""
    global _override
    previous = _override
    _override = _merge(DEFAULTS, patch or {}, strict=True)
    try:
        yield _override
    finally:
        _override = previous


def set_test_override(value: Optional[Dict[str, Any]]) -> None:
    global _override
    _override = value
