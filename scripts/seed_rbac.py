"""
Script khởi tạo / đồng bộ dữ liệu RBAC theo danh mục app/configs/permissions.py.

- Tạo các permission & role hệ thống (ADMIN, OWNER, STAFF) còn thiếu.
- Quyền mới được gán cho role mặc định; quyền Admin đã chỉnh trên ma trận được giữ nguyên.
- Gán role OWNER cho các tài khoản chưa có role.

Server cũng tự chạy bước đồng bộ này khi khởi động, script dùng khi cần chạy tay.

Cách dùng:
    python scripts/seed_rbac.py              # đồng bộ an toàn
    python scripts/seed_rbac.py --reset      # đặt lại quyền của role hệ thống về đúng mặc định
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.configs.database import SessionLocal
from app.configs.permissions import DEFAULT_ROLE_PERMISSIONS, FALLBACK_ROLE
from app.models.role_permission_model import Permission, Role
from app.models.user_model import User
from app.services.permission_service import PermissionService


def seed_rbac(reset_defaults: bool = False):
    db = SessionLocal()
    try:
        print("[SEED] Đồng bộ danh mục quyền...")
        summary = PermissionService.sync_catalog(db)
        for key, items in summary.items():
            if items:
                print(f" -> {key}: {', '.join(items)}")

        if reset_defaults:
            perms = {p.code: p for p in db.query(Permission).all()}
            for role_name, codes in DEFAULT_ROLE_PERMISSIONS.items():
                role = db.query(Role).filter(Role.role_name == role_name).first()
                role.permissions = [perms[c] for c in codes if c in perms]
                print(f" -> Đặt lại {role_name}: {len(role.permissions)} quyền")
            db.commit()

        fallback = db.query(Role).filter(Role.role_name == FALLBACK_ROLE).first()
        updated = (
            db.query(User)
            .filter(User.role_id.is_(None))
            .update({User.role_id: fallback.role_id}, synchronize_session=False)
        )
        db.commit()
        PermissionService.clear_cache()
        print(f"[SEED] Hoàn thành! Đã gán role {FALLBACK_ROLE} cho {updated} tài khoản chưa có role.")
    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_rbac(reset_defaults="--reset" in sys.argv)
