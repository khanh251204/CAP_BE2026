"""
Script khởi tạo (seed) dữ liệu ban đầu cho hệ thống RBAC:
- Danh mục Permissions (User, Product, Transaction, Inventory, Debt, Report, System)
- Các Roles mặc định: ADMIN, OWNER, STAFF
- Gán toàn bộ quyền cho ADMIN, gán quyền nghiệp vụ cho OWNER, gán quyền bán hàng cơ bản cho STAFF
- Tự động map User hiện tại theo role text sang role_id tương ứng
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.configs.database import SessionLocal
from app.models.role_permission_model import Role, Permission
from app.models.user_model import User

INITIAL_PERMISSIONS = [
    # USER Module
    {"code": "user:read", "module": "USER", "description": "Xem danh sách và thông tin người dùng"},
    {"code": "user:create", "module": "USER", "description": "Tạo tài khoản người dùng / nhân viên mới"},
    {"code": "user:update", "module": "USER", "description": "Cập nhật thông tin người dùng"},
    {"code": "user:delete", "module": "USER", "description": "Xóa hoặc vô hiệu hóa người dùng"},
    {"code": "user:assign_role", "module": "USER", "description": "Phân vai trò và quyền hạn cho người dùng"},

    # PRODUCT Module
    {"code": "product:read", "module": "PRODUCT", "description": "Xem danh sách và chi tiết sản phẩm"},
    {"code": "product:create", "module": "PRODUCT", "description": "Thêm sản phẩm mới"},
    {"code": "product:update", "module": "PRODUCT", "description": "Cập nhật thông tin sản phẩm"},
    {"code": "product:delete", "module": "PRODUCT", "description": "Xóa hoặc ngừng kinh doanh sản phẩm"},

    # TRANSACTION Module
    {"code": "transaction:read", "module": "TRANSACTION", "description": "Xem lịch sử giao dịch và hóa đơn"},
    {"code": "transaction:create", "module": "TRANSACTION", "description": "Tạo giao dịch bán/mua hàng"},
    {"code": "transaction:update", "module": "TRANSACTION", "description": "Sửa đổi giao dịch"},
    {"code": "transaction:delete", "module": "TRANSACTION", "description": "Hủy hoặc xóa giao dịch"},

    # INVENTORY Module
    {"code": "inventory:read", "module": "INVENTORY", "description": "Xem tồn kho và lịch sử xuất nhập"},
    {"code": "inventory:manage", "module": "INVENTORY", "description": "Nhập hàng, kiểm kho, điều chỉnh kho"},

    # DEBT Module
    {"code": "debt:read", "module": "DEBT", "description": "Xem công nợ khách hàng và nhà cung cấp"},
    {"code": "debt:manage", "module": "DEBT", "description": "Ghi nợ, thu nợ, trả nợ"},

    # REPORT Module
    {"code": "report:read", "module": "REPORT", "description": "Xem báo cáo doanh thu, chi phí, lợi nhuận"},
    {"code": "report:closing", "module": "REPORT", "description": "Thực hiện chốt sổ định kỳ"},

    # SYSTEM & RBAC Module
    {"code": "rbac:manage", "module": "SYSTEM", "description": "Quản lý vai trò và phân quyền (RBAC)"},
    {"code": "system:log_read", "module": "SYSTEM", "description": "Xem nhật ký hệ thống và audit log"},
]

def seed_rbac():
    db = SessionLocal()
    try:
        print("[SEED] Bắt đầu khởi tạo dữ liệu RBAC...")

        # 1. Seed Permissions
        perm_map = {}
        for p_data in INITIAL_PERMISSIONS:
            perm = db.query(Permission).filter(Permission.code == p_data["code"]).first()
            if not perm:
                perm = Permission(
                    code=p_data["code"],
                    module=p_data["module"],
                    description=p_data["description"]
                )
                db.add(perm)
                db.flush()
                print(f" -> Đã tạo permission: {perm.code}")
            perm_map[perm.code] = perm

        # 2. Seed Roles
        roles_config = [
            {
                "name": "ADMIN",
                "desc": "Quản trị viên toàn hệ thống, toàn quyền cấu hình và quản lý",
                "is_system": True,
                "perms": list(perm_map.keys())  # Toàn bộ quyền
            },
            {
                "name": "OWNER",
                "desc": "Chủ cửa hàng / Quản lý kinh doanh (quản lý sản phẩm, đơn hàng, công nợ, báo cáo)",
                "is_system": True,
                "perms": [
                    "user:read", "user:create", "user:update",
                    "product:read", "product:create", "product:update", "product:delete",
                    "transaction:read", "transaction:create", "transaction:update", "transaction:delete",
                    "inventory:read", "inventory:manage",
                    "debt:read", "debt:manage",
                    "report:read", "report:closing"
                ]
            },
            {
                "name": "STAFF",
                "desc": "Nhân viên bán hàng / Thu ngân (tạo đơn, xem tồn kho cơ bản)",
                "is_system": True,
                "perms": [
                    "product:read",
                    "transaction:read", "transaction:create",
                    "inventory:read",
                    "debt:read"
                ]
            }
        ]

        role_objs = {}
        for r_data in roles_config:
            role = db.query(Role).filter(Role.role_name == r_data["name"]).first()
            if not role:
                role = Role(
                    role_name=r_data["name"],
                    description=r_data["desc"],
                    is_system=r_data["is_system"]
                )
                db.add(role)
                db.flush()
                print(f" -> Đã tạo role: {role.role_name}")

            # Gán quyền
            current_perm_codes = {p.code for p in role.permissions}
            for code in r_data["perms"]:
                if code in perm_map and code not in current_perm_codes:
                    role.permissions.append(perm_map[code])

            role_objs[r_data["name"]] = role

        db.commit()

        # 3. Đồng bộ User hiện tại vào Role tương ứng
        admin_role = role_objs.get("ADMIN")
        owner_role = role_objs.get("OWNER")
        staff_role = role_objs.get("STAFF")

        users = db.query(User).all()
        updated_count = 0
        for u in users:
            r_str = str(u.role or "").strip().upper()
            target_role = None
            if r_str in ("ADMIN", "SUPERADMIN"):
                target_role = admin_role
            elif r_str in ("STAFF", "CASHIER"):
                target_role = staff_role
            else:
                target_role = owner_role  # Mặc định người dùng kinh doanh độc lập là OWNER

            if target_role and u.role_id != target_role.role_id:
                u.role_id = target_role.role_id
                u.role = target_role.role_name
                updated_count += 1

        db.commit()
        print(f"[SEED] Hoàn thành! Đã cập nhật role_id cho {updated_count} người dùng.")

    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_rbac()
