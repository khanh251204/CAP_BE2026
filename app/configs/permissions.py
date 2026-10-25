"""
Danh mục quyền (Permission Catalog) — nguồn sự thật duy nhất cho RBAC.

- PERMISSIONS: toàn bộ mã quyền của hệ thống, gom theo module.
- DEFAULT_ROLE_PERMISSIONS: quyền mặc định của các role hệ thống.
  Chỉ được gán tự động khi mã quyền được TẠO MỚI (xem PermissionService.sync_catalog),
  nên nếu Admin đã bỏ bớt quyền của một role thì lần khởi động sau không tự cấp lại.
- INTENT_PERMISSIONS: quyền cần có để xác nhận (commit) từng intent của AI Agent,
  để thao tác bằng giọng nói không vượt quyền so với thao tác bằng tay.

Quy ước mã quyền: "<module>:<hành động>". Quyền "admin_*" chỉ dành cho trang quản trị
(dữ liệu của mọi người dùng) — không bao giờ cấp cho OWNER/STAFF.
"""
from typing import Dict, List

PERMISSIONS: List[Dict[str, str]] = [
    # ===================== NGHIỆP VỤ CỬA HÀNG (dữ liệu của chính user) =====================
    # PRODUCT
    {"code": "product:read", "module": "PRODUCT", "description": "Xem danh sách và chi tiết sản phẩm"},
    {"code": "product:create", "module": "PRODUCT", "description": "Thêm sản phẩm mới"},
    {"code": "product:update", "module": "PRODUCT", "description": "Cập nhật thông tin sản phẩm"},
    {"code": "product:delete", "module": "PRODUCT", "description": "Xóa hoặc ngừng kinh doanh sản phẩm"},

    # INVENTORY
    {"code": "inventory:read", "module": "INVENTORY", "description": "Xem tồn kho, cảnh báo tồn kho và lịch sử xuất nhập"},
    {"code": "inventory:manage", "module": "INVENTORY", "description": "Kiểm kho, điều chỉnh kho, nhập/xuất kho thủ công, báo hàng hỏng"},

    # TRANSACTION
    {"code": "transaction:read", "module": "TRANSACTION", "description": "Xem lịch sử giao dịch và hóa đơn"},
    {"code": "transaction:create", "module": "TRANSACTION", "description": "Tạo giao dịch bán hàng"},
    {"code": "transaction:purchase", "module": "TRANSACTION", "description": "Tạo giao dịch mua hàng / nhập hàng từ nhà cung cấp"},
    {"code": "transaction:update", "module": "TRANSACTION", "description": "Sửa đổi giao dịch"},
    {"code": "transaction:delete", "module": "TRANSACTION", "description": "Hủy hoặc xóa giao dịch"},

    # EXPENSE
    {"code": "expense:create", "module": "EXPENSE", "description": "Ghi nhận chi phí kinh doanh"},

    # CUSTOMER
    {"code": "customer:read", "module": "CUSTOMER", "description": "Xem danh sách và chi tiết khách hàng"},
    {"code": "customer:manage", "module": "CUSTOMER", "description": "Thêm, sửa, xóa khách hàng"},

    # SUPPLIER
    {"code": "supplier:read", "module": "SUPPLIER", "description": "Xem danh sách và chi tiết nhà cung cấp"},
    {"code": "supplier:manage", "module": "SUPPLIER", "description": "Thêm, sửa, xóa nhà cung cấp"},

    # DEBT
    {"code": "debt:read", "module": "DEBT", "description": "Xem công nợ khách hàng và nhà cung cấp"},
    {"code": "debt:manage", "module": "DEBT", "description": "Ghi nợ, thu nợ, trả nợ"},

    # REPORT
    {"code": "report:read", "module": "REPORT", "description": "Xem báo cáo doanh thu, chi phí, lợi nhuận, tồn kho"},

    # CLOSING
    {"code": "closing:read", "module": "CLOSING", "description": "Xem lịch sử chốt sổ và báo cáo chốt sổ"},
    {"code": "closing:manage", "module": "CLOSING", "description": "Thực hiện chốt sổ định kỳ, gửi lại báo cáo"},
    {"code": "closing:reopen", "module": "CLOSING", "description": "Mở lại / chốt lại kỳ đã chốt sổ"},
    {"code": "closing:settings", "module": "CLOSING", "description": "Cấu hình tự động chốt sổ"},

    # VOICE / AI AGENT
    {"code": "voice:use", "module": "VOICE", "description": "Dùng trợ lý giọng nói (nhận dạng giọng nói, phân tích, xác nhận giao dịch AI)"},

    # USER (tài khoản trong cửa hàng — dành cho tính năng quản lý nhân viên)
    {"code": "user:read", "module": "USER", "description": "Xem danh sách và thông tin người dùng"},
    {"code": "user:create", "module": "USER", "description": "Tạo tài khoản người dùng / nhân viên mới"},
    {"code": "user:update", "module": "USER", "description": "Cập nhật thông tin người dùng"},
    {"code": "user:delete", "module": "USER", "description": "Xóa hoặc vô hiệu hóa người dùng"},
    {"code": "user:assign_role", "module": "USER", "description": "Phân vai trò và quyền hạn cho người dùng"},

    # ===================== QUẢN TRỊ HỆ THỐNG (dữ liệu của mọi user) =====================
    {"code": "admin_dashboard:read", "module": "ADMIN_DASHBOARD", "description": "Xem dashboard quản trị toàn hệ thống"},

    {"code": "admin_user:read", "module": "ADMIN_USER", "description": "Xem danh sách và chi tiết mọi người dùng"},
    {"code": "admin_user:manage", "module": "ADMIN_USER", "description": "Khóa / mở khóa tài khoản người dùng"},

    {"code": "admin_product:read", "module": "ADMIN_PRODUCT", "description": "Xem sản phẩm của mọi người dùng"},
    {"code": "admin_product:manage", "module": "ADMIN_PRODUCT", "description": "Bật / tắt trạng thái sản phẩm của người dùng"},

    {"code": "admin_transaction:read", "module": "ADMIN_TRANSACTION", "description": "Xem giao dịch của mọi người dùng"},

    {"code": "admin_voice:read", "module": "ADMIN_VOICE", "description": "Xem bản ghi giọng nói, kết quả AI và nghe lại audio"},

    {"code": "admin_dataset:read", "module": "ADMIN_DATASET", "description": "Xem dataset huấn luyện AI"},
    {"code": "admin_dataset:export", "module": "ADMIN_DATASET", "description": "Xuất dataset huấn luyện AI"},
    {"code": "admin_dataset:manage", "module": "ADMIN_DATASET", "description": "Đưa bản ghi giọng nói vào Data Lake"},

    {"code": "admin_notification:read", "module": "ADMIN_NOTIFICATION", "description": "Xem thông báo và thống kê thông báo"},
    {"code": "admin_notification:manage", "module": "ADMIN_NOTIFICATION", "description": "Gửi, sửa, xóa, dọn dẹp thông báo"},

    {"code": "admin_closing:read", "module": "ADMIN_CLOSING", "description": "Xem chốt sổ, email báo cáo và cấu hình chốt sổ của mọi người dùng"},
    {"code": "admin_closing:manage", "module": "ADMIN_CLOSING", "description": "Mở lại / chốt lại kỳ, gửi lại email, sửa cấu hình chốt sổ của người dùng"},

    {"code": "system:log_read", "module": "SYSTEM", "description": "Xem nhật ký hệ thống và audit log"},
    {"code": "rbac:read", "module": "SYSTEM", "description": "Xem vai trò và ma trận phân quyền"},
    {"code": "rbac:manage", "module": "SYSTEM", "description": "Tạo / sửa / xóa vai trò, phân quyền và gán vai trò cho người dùng"},
]

PERMISSION_CODES = {p["code"] for p in PERMISSIONS}

# Mã quyền cũ đã đổi tên: {mã cũ: mã mới}. Bản ghi cũ được đổi mã tại chỗ
# nên các role đang có quyền cũ giữ nguyên liên kết.
RENAMED_PERMISSIONS: Dict[str, str] = {
    "report:closing": "closing:manage",
}

_STORE_PERMISSIONS = [p["code"] for p in PERMISSIONS if not p["code"].startswith(("admin_", "system:", "rbac:"))]

DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    # ADMIN luôn có toàn quyền (bỏ qua kiểm tra), danh sách này chỉ để hiển thị ma trận quyền
    "ADMIN": sorted(PERMISSION_CODES),
    # Chủ cửa hàng: toàn bộ nghiệp vụ của cửa hàng mình, không có quyền quản trị hệ thống
    "OWNER": [c for c in _STORE_PERMISSIONS if c not in ("user:delete", "user:assign_role")],
    # Nhân viên bán hàng / thu ngân
    "STAFF": [
        "product:read",
        "inventory:read",
        "transaction:read",
        "transaction:create",
        "customer:read",
        "debt:read",
        "voice:use",
    ],
}

# Role dùng khi tài khoản chưa được gán role (dữ liệu cũ trước khi có RBAC).
FALLBACK_ROLE = "OWNER"

# Quyền cần có để xác nhận từng intent của AI Agent (/agent/confirm).
INTENT_PERMISSIONS: Dict[str, str] = {
    "ban_hang": "transaction:create",
    "mua_hang": "transaction:purchase",
    "nhap_hang": "transaction:purchase",
    "chi_phi": "expense:create",
    "chi_tien": "expense:create",
    "ghi_no_khach_hang": "debt:manage",
    "khach_ghi_no": "debt:manage",
    "thu_no_khach_hang": "debt:manage",
    "thu_no_khach": "debt:manage",
    "ghi_no_nha_cung_cap": "debt:manage",
    "ncc_ghi_no": "debt:manage",
    "tra_no_nha_cung_cap": "debt:manage",
    "tra_no_ncc": "debt:manage",
    "them_san_pham": "product:create",
    "sua_san_pham": "product:update",
    "xoa_san_pham": "product:delete",
    "nhap_kho": "inventory:manage",
    "xuat_kho": "inventory:manage",
    "hang_hong": "inventory:manage",
    "kiem_kho": "inventory:read",
    "tim_san_pham": "product:read",
    "xem_san_pham": "product:read",
    "bao_cao": "report:read",
}
