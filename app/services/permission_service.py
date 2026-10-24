"""
Permission Service — tra cứu quyền của người dùng & đồng bộ danh mục quyền vào DB.

Quyền luôn được đọc từ DB (role hiện tại của user), không tin claim "role" trong JWT,
để việc hạ quyền / khóa quyền có hiệu lực ngay cả khi user còn giữ access token cũ.
Kết quả được cache ngắn (TTL) theo user để không tốn query mỗi request; RBACService
xóa cache ngay khi đổi quyền trong cùng tiến trình.
"""
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, FrozenSet, Optional, Tuple

from sqlalchemy.orm import Session

from app.configs.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    FALLBACK_ROLE,
    PERMISSIONS,
    RENAMED_PERMISSIONS,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30

SYSTEM_ROLE_DESCRIPTIONS = {
    "ADMIN": "Quản trị viên toàn hệ thống, toàn quyền cấu hình và quản lý",
    "OWNER": "Chủ cửa hàng / Quản lý kinh doanh (quản lý sản phẩm, đơn hàng, công nợ, báo cáo, chốt sổ)",
    "STAFF": "Nhân viên bán hàng / Thu ngân (bán hàng, xem tồn kho, xem khách hàng)",
}


@dataclass(frozen=True)
class UserAccess:
    user_id: int
    exists: bool
    role_name: str
    permissions: FrozenSet[str]
    is_locked: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role_name == "ADMIN"

    def has(self, code: str) -> bool:
        return self.is_admin or code in self.permissions


class PermissionService:
    _cache: Dict[int, Tuple[float, UserAccess]] = {}
    _lock = threading.Lock()

    # =============================================
    # TRA CỨU QUYỀN
    # =============================================
    @classmethod
    def get_user_access(cls, user_id: int, db: Optional[Session] = None) -> UserAccess:
        now = time.monotonic()
        with cls._lock:
            cached = cls._cache.get(user_id)
            if cached and cached[0] > now:
                return cached[1]

        access = cls._load_access(user_id, db)
        with cls._lock:
            cls._cache[user_id] = (now + CACHE_TTL_SECONDS, access)
        return access

    @classmethod
    def _load_access(cls, user_id: int, db: Optional[Session]) -> UserAccess:
        from app.models.role_permission_model import Role
        from app.models.user_model import User

        own_session = db is None
        if own_session:
            from app.configs.database import SessionLocal
            db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                return UserAccess(user_id, False, "", frozenset())
            # Admin khóa tài khoản -> chặn ngay cả khi access token cũ chưa hết hạn
            is_locked = bool(user.lock_until and user.lock_until > datetime.utcnow())

            role = user.role_rel
            if role is None:
                # Tài khoản cũ chưa gán role -> áp quyền của role mặc định
                role = db.query(Role).filter(Role.role_name == FALLBACK_ROLE).first()
                if role is None:
                    return UserAccess(
                        user_id, True, FALLBACK_ROLE,
                        frozenset(DEFAULT_ROLE_PERMISSIONS.get(FALLBACK_ROLE, [])),
                        is_locked,
                    )

            return UserAccess(
                user_id,
                True,
                str(role.role_name or "").strip().upper(),
                frozenset(p.code for p in role.permissions),
                is_locked,
            )
        finally:
            if own_session:
                db.close()

    @classmethod
    def has_permission(cls, user_id: int, code: str) -> bool:
        return cls.get_user_access(user_id).has(code)

    @classmethod
    def clear_cache(cls, user_id: Optional[int] = None) -> None:
        with cls._lock:
            if user_id is None:
                cls._cache.clear()
            else:
                cls._cache.pop(user_id, None)

    # =============================================
    # ĐỒNG BỘ DANH MỤC QUYỀN VÀO DB
    # =============================================
    @classmethod
    def sync_catalog(cls, db: Session) -> Dict[str, list]:
        """
        Idempotent, chạy lúc khởi động:
        1. Đổi mã các quyền đã đổi tên (giữ nguyên liên kết role).
        2. Tạo các quyền còn thiếu và cập nhật module/mô tả.
        3. Tạo các role hệ thống còn thiếu.
        4. Quyền MỚI TẠO được gán cho các role mặc định theo DEFAULT_ROLE_PERMISSIONS.
           Không đụng tới quyền đã có, nên các chỉnh sửa của Admin được giữ nguyên.
        """
        from app.models.role_permission_model import Permission, Role

        summary = {"renamed": [], "created_permissions": [], "created_roles": [], "granted": []}

        existing = {p.code: p for p in db.query(Permission).all()}

        for old_code, new_code in RENAMED_PERMISSIONS.items():
            if old_code in existing and new_code not in existing:
                perm = existing.pop(old_code)
                perm.code = new_code
                existing[new_code] = perm
                summary["renamed"].append(f"{old_code}->{new_code}")

        new_codes = set()
        for spec in PERMISSIONS:
            perm = existing.get(spec["code"])
            if perm is None:
                perm = Permission(code=spec["code"], module=spec["module"], description=spec["description"])
                db.add(perm)
                existing[spec["code"]] = perm
                new_codes.add(spec["code"])
                summary["created_permissions"].append(spec["code"])
            else:
                perm.module = spec["module"]
                perm.description = spec["description"]
        db.flush()

        roles = {r.role_name.upper(): r for r in db.query(Role).all()}
        for role_name in DEFAULT_ROLE_PERMISSIONS:
            if role_name not in roles:
                role = Role(
                    role_name=role_name,
                    description=SYSTEM_ROLE_DESCRIPTIONS.get(role_name),
                    is_system=True,
                )
                db.add(role)
                db.flush()
                roles[role_name] = role
                summary["created_roles"].append(role_name)

        for role_name, codes in DEFAULT_ROLE_PERMISSIONS.items():
            role = roles[role_name]
            is_new_role = role_name in summary["created_roles"]
            current = {p.code for p in role.permissions}
            for code in codes:
                if code in current:
                    continue
                if is_new_role or code in new_codes:
                    role.permissions.append(existing[code])
                    summary["granted"].append(f"{role_name}:{code}")

        db.commit()
        cls.clear_cache()
        return summary
