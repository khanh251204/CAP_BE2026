"""
Quản lý gói tính năng AI & phân quyền intent theo từng tài khoản (Admin -> Production Optimization).

- Admin có thể:
  1. Quản lý danh mục gói dịch vụ AI (lưu trong `App_Setting` khoá `"ai_plans"`):
     VD: `basic_50k` (2 intent: bán hàng, mua hàng), `standard` (7 intent Cap 1), `pro` (full 17 intent + multi-item + OCR).
  2. Gán gói HOẶC tùy chỉnh trực tiếp từng intent + `allow_multi_item` + `allow_ocr` cho từng tài khoản (`User_AI_Feature`).
  3. Gán nhanh hàng loạt (bulk assign) cho nhiều tài khoản.
- Trên luồng AI (`Agent.run`, `Agent._handle_analysis`, `confirm_action`, `ocr_route`):
  - Đọc cấu hình qua cache RAM ngắn hạn (TTL 30s) -> không tốn query DB trên mỗi câu nói.
  - Nếu `allowed_intents == []` -> chặn ngay trước khi gọi LLM (0 token, < 1ms).
  - Nếu `allowed_intents` bị giới hạn -> dựng system prompt rút gọn chỉ chứa đúng các intent được cấp -> giảm 50-65% token & latency.
  - Lỗi đọc DB hoặc user chưa có cấu hình -> fallback mặc định cho dùng đầy đủ (fail-open, tương thích ngược 100%).
"""
import copy
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai.prompts.builder import INTENT_ORDER, build_pruned_system_prompt, estimate_prompt_stats

logger = logging.getLogger(__name__)

AI_PLANS_SETTING_KEY = "ai_plans"
USER_CACHE_TTL_SECONDS = 30
PLAN_CACHE_TTL_SECONDS = 30


# =====================================================================
# DANH MỤC 17 INTENTS CHUẨN & ALIAS
# =====================================================================

INTENT_CATALOG: List[Dict[str, Any]] = [
    {"code": "ban_hang", "name": "Bán hàng", "group": "CORE_TRANSACTION", "aliases": [], "description": "Ghi nhận giao dịch bán hàng cho khách (tiền mặt, chuyển khoản, bán nợ)"},
    {"code": "mua_hang", "name": "Mua / Nhập hàng", "group": "CORE_TRANSACTION", "aliases": ["nhap_hang"], "description": "Ghi nhận mua/nhập hàng từ nhà cung cấp"},
    {"code": "chi_phi", "name": "Chi phí kinh doanh", "group": "CORE_TRANSACTION", "aliases": ["chi_tien"], "description": "Ghi nhận chi phí vận hành (điện, nước, mặt bằng, vận chuyển...)"},
    {"code": "khach_ghi_no", "name": "Ghi nợ khách hàng", "group": "DEBT", "aliases": ["ghi_no_khach_hang"], "description": "Ghi nhận khoản nợ phải thu từ khách hàng"},
    {"code": "thu_no_khach", "name": "Thu nợ khách hàng", "group": "DEBT", "aliases": ["thu_no_khach_hang"], "description": "Ghi nhận khách hàng thanh toán nợ"},
    {"code": "ghi_no_nha_cung_cap", "name": "Ghi nợ nhà cung cấp", "group": "DEBT", "aliases": ["ncc_ghi_no"], "description": "Ghi nhận khoản nợ phải trả nhà cung cấp"},
    {"code": "tra_no_nha_cung_cap", "name": "Trả nợ nhà cung cấp", "group": "DEBT", "aliases": ["thu_no_nha_cung_cap", "tra_no_ncc"], "description": "Ghi nhận thanh toán nợ cho nhà cung cấp"},
    {"code": "them_san_pham", "name": "Thêm sản phẩm", "group": "PRODUCT", "aliases": [], "description": "Tạo sản phẩm mới trong danh mục bằng giọng nói"},
    {"code": "sua_san_pham", "name": "Sửa sản phẩm", "group": "PRODUCT", "aliases": [], "description": "Cập nhật tên, đơn giá hoặc đơn vị sản phẩm"},
    {"code": "xoa_san_pham", "name": "Xóa sản phẩm", "group": "PRODUCT", "aliases": [], "description": "Ngừng kinh doanh / xóa mềm sản phẩm"},
    {"code": "tim_san_pham", "name": "Tìm kiếm sản phẩm", "group": "PRODUCT", "aliases": ["xem_san_pham"], "description": "Tra cứu thông tin và giá bán sản phẩm"},
    {"code": "nhap_kho", "name": "Nhập kho nội bộ", "group": "INVENTORY", "aliases": [], "description": "Nhập kho không mất tiền (tồn đầu, hàng tặng, khách trả lại, sản xuất xong)"},
    {"code": "xuat_kho", "name": "Xuất kho nội bộ", "group": "INVENTORY", "aliases": [], "description": "Xuất kho điều chuyển / sử dụng nội bộ"},
    {"code": "hang_hong", "name": "Báo hàng hỏng", "group": "INVENTORY", "aliases": [], "description": "Ghi nhận hàng tồn kho hư hỏng / hết hạn"},
    {"code": "kiem_kho", "name": "Kiểm kho / Hỏi tồn", "group": "INVENTORY", "aliases": [], "description": "Hỏi tồn kho hiện tại hoặc kiểm kê điều chỉnh số lượng thực tế"},
    {"code": "bao_cao", "name": "Báo cáo doanh thu", "group": "REPORT", "aliases": [], "description": "Xem nhanh doanh thu, chi phí, lợi nhuận định kỳ"},
    {"code": "chot_so", "name": "Chốt sổ theo kỳ", "group": "REPORT", "aliases": [], "description": "Xem trước và khóa sổ ngày / tháng / quý / năm"},
]

CANONICAL_INTENTS = frozenset(item["code"] for item in INTENT_CATALOG)
INTENT_LABELS: Dict[str, str] = {item["code"]: item["name"] for item in INTENT_CATALOG}

INTENT_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _item in INTENT_CATALOG:
    INTENT_ALIAS_TO_CANONICAL[_item["code"]] = _item["code"]
    for _alias in _item["aliases"]:
        INTENT_ALIAS_TO_CANONICAL[_alias] = _item["code"]


def canonicalize_intent(intent: Optional[str]) -> Optional[str]:
    if not intent or not isinstance(intent, str):
        return None
    key = intent.strip().lower()
    return INTENT_ALIAS_TO_CANONICAL.get(key)


def normalize_intent_list(intents: Optional[Iterable[str]], strict: bool = True) -> Optional[List[str]]:
    """
    Chuẩn hóa danh sách intent về tên canonical, giữ thứ tự chuẩn, loại trùng.
    - `intents is None` -> trả về `None` (nghĩa là không giới hạn — full 17 intents).
    - `strict=True`: ném ValueError nếu có mã intent không tồn tại.
    """
    if intents is None:
        return None
    seen: set[str] = set()
    invalid: List[str] = []
    for raw in intents:
        canon = canonicalize_intent(raw)
        if not canon:
            invalid.append(str(raw))
        else:
            seen.add(canon)
    if invalid and strict:
        raise ValueError(f"Intent không hợp lệ: {', '.join(invalid)}")
    return [code for code in INTENT_ORDER if code in seen]


# =====================================================================
# CÁC GÓI MẶC ĐỊNH (ADMIN CÓ THỂ SỬA / THÊM / XÓA)
# =====================================================================

DEFAULT_AI_PLANS: Dict[str, Dict[str, Any]] = {
    "locked": {
        "code": "locked",
        "name": "Khóa AI",
        "price_vnd": 0,
        "description": "Tắt hoàn toàn trợ lý AI (0 intent, không gọi LLM).",
        "allowed_intents": [],
        "allow_multi_item": False,
        "allow_ocr": False,
        "is_system": True,
    },
    "basic_50k": {
        "code": "basic_50k",
        "name": "Gói Cơ Bản 50K",
        "price_vnd": 50000,
        "description": "Xử lý 2 nghiệp vụ cốt lõi: Bán hàng & Mua/Nhập hàng. Tối ưu prompt rút gọn ~60%.",
        "allowed_intents": ["ban_hang", "mua_hang"],
        "allow_multi_item": False,
        "allow_ocr": False,
        "is_system": True,
    },
    "standard": {
        "code": "standard",
        "name": "Gói Tiêu Chuẩn",
        "price_vnd": 120000,
        "description": "7 nghiệp vụ giao dịch tài chính & công nợ cốt lõi (bán, mua, chi phí, 4 loại công nợ).",
        "allowed_intents": [
            "ban_hang",
            "mua_hang",
            "chi_phi",
            "khach_ghi_no",
            "thu_no_khach",
            "ghi_no_nha_cung_cap",
            "tra_no_nha_cung_cap",
        ],
        "allow_multi_item": True,
        "allow_ocr": False,
        "is_system": True,
    },
    "pro": {
        "code": "pro",
        "name": "Gói Toàn Diện (Pro)",
        "price_vnd": 250000,
        "description": "Mở khóa toàn bộ 17 nghiệp vụ AI, nhiều sản phẩm trong 1 câu và quét hóa đơn OCR.",
        "allowed_intents": None,  # None = không giới hạn (full 17 intents)
        "allow_multi_item": True,
        "allow_ocr": True,
        "is_system": True,
    },
}


# =====================================================================
# USER AI CONFIG + CACHE RAM (TTL 30s)
# =====================================================================

@dataclass(frozen=True)
class UserAIConfig:
    user_id: int
    plan_code: Optional[str] = None
    # None = full 17 intents (không giới hạn); tuple() = khóa toàn bộ AI
    allowed_intents: Optional[Tuple[str, ...]] = None
    allow_multi_item: bool = True
    allow_ocr: bool = True
    note: Optional[str] = None

    @property
    def is_unrestricted(self) -> bool:
        return self.allowed_intents is None

    @property
    def is_ai_locked(self) -> bool:
        return self.allowed_intents is not None and len(self.allowed_intents) == 0

    def is_intent_allowed(self, intent: Optional[str]) -> bool:
        if self.allowed_intents is None:
            return True
        canon = canonicalize_intent(intent)
        if not canon:
            return False
        return canon in self.allowed_intents

    def effective_intents(self) -> List[str]:
        if self.allowed_intents is None:
            return list(INTENT_ORDER)
        return list(self.allowed_intents)

    def build_system_prompt(self, current_date: Optional[str] = None) -> Optional[str]:
        """
        Trả về system prompt đã rút gọn theo cấu hình của user.
        - Trả về `None` nếu user dùng full mặc định (dùng `SYSTEM_PROMPT` gốc).
        - Trả về `""` nếu user bị khóa toàn bộ AI (0 intent).
        """
        if self.is_ai_locked:
            return ""
        if self.allowed_intents is None and self.allow_multi_item:
            return None
        intents_for_prompt = self.allowed_intents if self.allowed_intents is not None else INTENT_ORDER
        return build_pruned_system_prompt(
            allowed_intents=intents_for_prompt,
            allow_multi_item=self.allow_multi_item,
            current_date=current_date,
        )


_user_cache_lock = threading.Lock()
_user_cache: Dict[int, Tuple[float, UserAIConfig]] = {}

_plan_cache_lock = threading.Lock()
_plan_cache: Dict[str, Any] = {"expires": 0.0, "value": None}


def invalidate_user_cache(user_id: Optional[int] = None) -> None:
    with _user_cache_lock:
        if user_id is None:
            _user_cache.clear()
        else:
            _user_cache.pop(int(user_id), None)


def invalidate_plan_cache() -> None:
    with _plan_cache_lock:
        _plan_cache["expires"] = 0.0
        _plan_cache["value"] = None


def _row_to_config(user_id: int, row: Any) -> UserAIConfig:
    if row is None:
        return UserAIConfig(user_id=user_id)
    normalized = normalize_intent_list(row.allowed_intents, strict=False)
    return UserAIConfig(
        user_id=user_id,
        plan_code=row.plan_code,
        allowed_intents=tuple(normalized) if normalized is not None else None,
        allow_multi_item=bool(row.allow_multi_item),
        allow_ocr=bool(row.allow_ocr),
        note=row.note,
    )


def _load_user_config_from_db(user_id: int) -> UserAIConfig:
    from app.configs.database import get_db_session
    from app.models.user_ai_feature_model import UserAIFeature

    db = get_db_session()
    try:
        row = db.query(UserAIFeature).filter(UserAIFeature.user_id == user_id).first()
        return _row_to_config(user_id, row)
    finally:
        db.close()


def get_user_ai_config(user_id: int, db: Optional[Session] = None) -> UserAIConfig:
    """
    Lấy cấu hình AI hiệu lực của 1 user.
    - Nếu truyền `db`: đọc trực tiếp từ DB (dùng trong admin API / confirm).
    - Nếu không truyền `db`: dùng cache TTL 30s; lỗi DB thì fail-open về mặc định (không làm gãy luồng chính / unit test).
    """
    uid = int(user_id)
    if db is not None:
        from app.models.user_ai_feature_model import UserAIFeature
        row = db.query(UserAIFeature).filter(UserAIFeature.user_id == uid).first()
        cfg = _row_to_config(uid, row)
        with _user_cache_lock:
            _user_cache[uid] = (time.monotonic() + USER_CACHE_TTL_SECONDS, cfg)
        return cfg

    now = time.monotonic()
    with _user_cache_lock:
        cached = _user_cache.get(uid)
        if cached is not None and now < cached[0]:
            return cached[1]

    try:
        cfg = _load_user_config_from_db(uid)
    except Exception as exc:
        logger.debug("Không đọc được User_AI_Feature cho user_id=%s, dùng mặc định: %s", uid, exc)
        return UserAIConfig(user_id=uid)

    with _user_cache_lock:
        _user_cache[uid] = (now + USER_CACHE_TTL_SECONDS, cfg)
    return cfg


def is_intent_allowed(user_id: int, intent: Optional[str], db: Optional[Session] = None) -> bool:
    return get_user_ai_config(user_id, db=db).is_intent_allowed(intent)


def is_ocr_allowed(user_id: int, db: Optional[Session] = None) -> bool:
    return get_user_ai_config(user_id, db=db).allow_ocr


def locked_intent_message(intent: Optional[str], plan_code: Optional[str] = None) -> str:
    canon = canonicalize_intent(intent)
    label = INTENT_LABELS.get(canon or "", intent or "nghiệp vụ này")
    if plan_code:
        return (
            f"Gói '{plan_code}' hiện tại chưa hỗ trợ chức năng '{label}'. "
            "Vui lòng nâng cấp gói hoặc liên hệ quản trị viên để mở khóa."
        )
    return (
        f"Tài khoản hiện chưa được mở chức năng '{label}'. "
        "Vui lòng nâng cấp gói hoặc liên hệ quản trị viên để mở khóa."
    )


# =====================================================================
# QUẢN LÝ GÓI AI (PLANS) LƯU TRONG App_Setting
# =====================================================================

def _merge_plans(stored: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    plans = copy.deepcopy(DEFAULT_AI_PLANS)
    if not isinstance(stored, dict):
        return plans
    for code, raw in stored.items():
        if not isinstance(raw, dict):
            continue
        is_system = code in DEFAULT_AI_PLANS
        allowed = normalize_intent_list(raw.get("allowed_intents"), strict=False)
        plans[code] = {
            "code": code,
            "name": str(raw.get("name") or code),
            "price_vnd": int(raw.get("price_vnd") or 0),
            "description": str(raw.get("description") or ""),
            "allowed_intents": allowed,
            "allow_multi_item": bool(raw.get("allow_multi_item", True)),
            "allow_ocr": bool(raw.get("allow_ocr", True)),
            "is_system": is_system,
        }
    return plans


def get_plans(db: Optional[Session] = None) -> Dict[str, Dict[str, Any]]:
    if db is not None:
        from app.models.app_setting_model import AppSetting
        row = db.query(AppSetting).filter(AppSetting.setting_key == AI_PLANS_SETTING_KEY).first()
        plans = _merge_plans(row.value if row else None)
        with _plan_cache_lock:
            _plan_cache["value"] = plans
            _plan_cache["expires"] = time.monotonic() + PLAN_CACHE_TTL_SECONDS
        return copy.deepcopy(plans)

    now = time.monotonic()
    with _plan_cache_lock:
        if _plan_cache["value"] is not None and now < _plan_cache["expires"]:
            return copy.deepcopy(_plan_cache["value"])

    try:
        from app.configs.database import get_db_session
        from app.models.app_setting_model import AppSetting
        sess = get_db_session()
        try:
            row = sess.query(AppSetting).filter(AppSetting.setting_key == AI_PLANS_SETTING_KEY).first()
            plans = _merge_plans(row.value if row else None)
        finally:
            sess.close()
    except Exception:
        plans = copy.deepcopy(DEFAULT_AI_PLANS)

    with _plan_cache_lock:
        _plan_cache["value"] = plans
        _plan_cache["expires"] = now + PLAN_CACHE_TTL_SECONDS
    return copy.deepcopy(plans)


def _save_plans_to_db(db: Session, plans: Dict[str, Dict[str, Any]], admin_id: Optional[int]) -> None:
    from app.models.app_setting_model import AppSetting

    row = db.query(AppSetting).filter(AppSetting.setting_key == AI_PLANS_SETTING_KEY).first()
    if row is None:
        row = AppSetting(
            setting_key=AI_PLANS_SETTING_KEY,
            value=plans,
            updated_at=datetime.now(),
            updated_by=admin_id,
        )
        db.add(row)
    else:
        row.value = plans
        row.updated_at = datetime.now()
        row.updated_by = admin_id
    db.commit()
    invalidate_plan_cache()


def upsert_plan(
    db: Session,
    plan_code: str,
    name: str,
    price_vnd: int,
    description: str,
    allowed_intents: Optional[List[str]],
    allow_multi_item: bool,
    allow_ocr: bool,
    admin_id: Optional[int] = None,
) -> Dict[str, Any]:
    code = plan_code.strip().lower()
    if not code or len(code) > 64:
        raise ValueError("Mã gói (plan_code) phải từ 1 đến 64 ký tự")
    if price_vnd < 0:
        raise ValueError("Giá gói không được âm")

    normalized = normalize_intent_list(allowed_intents, strict=True)
    plans = get_plans(db)
    plans[code] = {
        "code": code,
        "name": name.strip() or code,
        "price_vnd": int(price_vnd),
        "description": description.strip(),
        "allowed_intents": normalized,
        "allow_multi_item": bool(allow_multi_item),
        "allow_ocr": bool(allow_ocr),
        "is_system": code in DEFAULT_AI_PLANS,
    }
    _save_plans_to_db(db, plans, admin_id)
    return annotate_plan_with_stats(plans[code])


def delete_plan(db: Session, plan_code: str, admin_id: Optional[int] = None) -> bool:
    code = plan_code.strip().lower()
    if code in DEFAULT_AI_PLANS:
        raise ValueError(f"Không thể xóa gói mặc định hệ thống '{code}' (chỉ có thể chỉnh sửa)")
    plans = get_plans(db)
    if code not in plans:
        return False
    del plans[code]
    _save_plans_to_db(db, plans, admin_id)
    return True


def annotate_plan_with_stats(plan: Dict[str, Any]) -> Dict[str, Any]:
    from app.ai.prompts.main import SYSTEM_PROMPT

    allowed = plan.get("allowed_intents")
    allow_multi = bool(plan.get("allow_multi_item", True))
    if allowed is None and allow_multi:
        active_prompt = SYSTEM_PROMPT
    elif allowed is not None and len(allowed) == 0:
        active_prompt = ""
    else:
        active_prompt = build_pruned_system_prompt(
            allowed_intents=allowed if allowed is not None else INTENT_ORDER,
            allow_multi_item=allow_multi,
        )
    out = copy.deepcopy(plan)
    out["intent_count"] = len(INTENT_ORDER) if allowed is None else len(allowed)
    out["prompt_stats"] = estimate_prompt_stats(SYSTEM_PROMPT, active_prompt)
    return out


# =====================================================================
# ADMIN: QUẢN LÝ CẤU HÌNH AI THEO TỪNG USER
# =====================================================================

def format_user_ai_feature(user: Any, cfg: UserAIConfig, updated_at: Any = None, updated_by: Any = None) -> Dict[str, Any]:
    from app.ai.prompts.main import SYSTEM_PROMPT

    active_prompt = cfg.build_system_prompt()
    if active_prompt is None:
        active_prompt = SYSTEM_PROMPT

    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "business_type": user.business_type,
        "plan_code": cfg.plan_code,
        "is_unrestricted": cfg.is_unrestricted,
        "is_ai_locked": cfg.is_ai_locked,
        "allowed_intents": list(cfg.allowed_intents) if cfg.allowed_intents is not None else None,
        "effective_intents": cfg.effective_intents(),
        "intent_count": len(cfg.effective_intents()),
        "allow_multi_item": cfg.allow_multi_item,
        "allow_ocr": cfg.allow_ocr,
        "note": cfg.note,
        "prompt_stats": estimate_prompt_stats(SYSTEM_PROMPT, active_prompt),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "updated_by": updated_by,
    }


def list_user_ai_features(
    db: Session,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    plan_code: Optional[str] = None,
) -> Dict[str, Any]:
    from sqlalchemy import or_
    from app.models.user_model import User
    from app.models.user_ai_feature_model import UserAIFeature

    query = db.query(User, UserAIFeature).outerjoin(UserAIFeature, User.user_id == UserAIFeature.user_id)

    if search and search.strip():
        kw = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.full_name.ilike(kw),
                User.email.ilike(kw),
                User.phone_number.ilike(kw),
            )
        )
    if plan_code is not None and plan_code.strip():
        pc = plan_code.strip().lower()
        if pc == "default":
            query = query.filter(UserAIFeature.user_id.is_(None))
        elif pc == "custom":
            query = query.filter(UserAIFeature.user_id.isnot(None), UserAIFeature.plan_code.is_(None))
        else:
            query = query.filter(UserAIFeature.plan_code == pc)

    total = query.count()
    rows = (
        query.order_by(User.user_id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        format_user_ai_feature(
            user=u,
            cfg=_row_to_config(u.user_id, feat),
            updated_at=feat.updated_at if feat else None,
            updated_by=feat.updated_by if feat else None,
        )
        for u, feat in rows
    ]
    total_pages = max(1, (total + limit - 1) // limit)
    return {
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_items": total,
            "total_pages": total_pages,
        },
    }


def get_user_ai_feature_detail(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    from app.models.user_model import User
    from app.models.user_ai_feature_model import UserAIFeature

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None
    feat = db.query(UserAIFeature).filter(UserAIFeature.user_id == user_id).first()
    return format_user_ai_feature(
        user=user,
        cfg=_row_to_config(user.user_id, feat),
        updated_at=feat.updated_at if feat else None,
        updated_by=feat.updated_by if feat else None,
    )


def set_user_ai_feature(
    db: Session,
    user_id: int,
    plan_code: Optional[str] = None,
    allowed_intents: Any = ...,  # sentinel Ellipsis = không gửi
    allow_multi_item: Optional[bool] = None,
    allow_ocr: Optional[bool] = None,
    note: Optional[str] = None,
    admin_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Cập nhật quyền AI cho 1 tài khoản:
    - Nếu truyền `plan_code`: áp toàn bộ cấu hình của gói đó làm nền, đồng thời cho phép override thêm
      `allowed_intents` / `allow_multi_item` / `allow_ocr` nếu admin gửi kèm.
    - Nếu không truyền `plan_code`: tùy chỉnh trực tiếp (`plan_code = None`, custom).
    """
    from app.models.user_model import User
    from app.models.user_ai_feature_model import UserAIFeature

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None

    plans = get_plans(db)
    resolved_plan_code: Optional[str] = None
    resolved_intents: Optional[List[str]] = None
    resolved_multi = True
    resolved_ocr = True

    if plan_code is not None and plan_code.strip():
        code = plan_code.strip().lower()
        if code not in plans:
            raise ValueError(f"Gói AI không tồn tại: '{code}'")
        plan = plans[code]
        resolved_plan_code = code
        resolved_intents = copy.deepcopy(plan["allowed_intents"])
        resolved_multi = bool(plan["allow_multi_item"])
        resolved_ocr = bool(plan["allow_ocr"])

    # Cho phép override trực tiếp từng trường nếu admin gửi kèm
    if allowed_intents is not ...:
        resolved_intents = normalize_intent_list(allowed_intents, strict=True)
    if allow_multi_item is not None:
        resolved_multi = bool(allow_multi_item)
    if allow_ocr is not None:
        resolved_ocr = bool(allow_ocr)

    row = db.query(UserAIFeature).filter(UserAIFeature.user_id == user_id).first()
    now = datetime.now()
    if row is None:
        row = UserAIFeature(
            user_id=user_id,
            plan_code=resolved_plan_code,
            allowed_intents=resolved_intents,
            allow_multi_item=resolved_multi,
            allow_ocr=resolved_ocr,
            note=note,
            updated_at=now,
            updated_by=admin_id,
        )
        db.add(row)
    else:
        row.plan_code = resolved_plan_code
        row.allowed_intents = resolved_intents
        row.allow_multi_item = resolved_multi
        row.allow_ocr = resolved_ocr
        if note is not None:
            row.note = note
        row.updated_at = now
        row.updated_by = admin_id

    db.commit()
    db.refresh(row)
    invalidate_user_cache(user_id)

    return format_user_ai_feature(
        user=user,
        cfg=_row_to_config(user.user_id, row),
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


def bulk_assign_user_ai_features(
    db: Session,
    user_ids: List[int],
    plan_code: Optional[str] = None,
    allowed_intents: Any = ...,
    allow_multi_item: Optional[bool] = None,
    allow_ocr: Optional[bool] = None,
    note: Optional[str] = None,
    admin_id: Optional[int] = None,
) -> Dict[str, Any]:
    updated: List[int] = []
    not_found: List[int] = []
    for uid in dict.fromkeys(user_ids):
        res = set_user_ai_feature(
            db=db,
            user_id=uid,
            plan_code=plan_code,
            allowed_intents=allowed_intents,
            allow_multi_item=allow_multi_item,
            allow_ocr=allow_ocr,
            note=note,
            admin_id=admin_id,
        )
        if res is None:
            not_found.append(uid)
        else:
            updated.append(uid)
    return {"updated_user_ids": updated, "not_found_user_ids": not_found, "updated_count": len(updated)}


def reset_user_ai_feature(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    from app.models.user_model import User
    from app.models.user_ai_feature_model import UserAIFeature

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None
    db.query(UserAIFeature).filter(UserAIFeature.user_id == user_id).delete()
    db.commit()
    invalidate_user_cache(user_id)
    return format_user_ai_feature(user=user, cfg=UserAIConfig(user_id=user.user_id))
