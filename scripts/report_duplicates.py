"""
Liệt kê Sản phẩm / Khách hàng / Nhà cung cấp đang bị TRÙNG trong DB (dữ liệu tạo trước khi có chặn trùng).

Chỉ đọc, không sửa dữ liệu. Dùng kết quả để gộp tay (chuyển giao dịch/công nợ sang một bản ghi
rồi xóa/ngừng bản còn lại), vì gộp tự động dễ làm sai lịch sử kế toán.

Cách dùng:
    python scripts/report_duplicates.py
    python scripts/report_duplicates.py --user 12
"""
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.configs.database import SessionLocal
from app.models.customer_model import Customer
from app.models.product_model import Product
from app.models.supplier_model import Supplier
from app.services.duplicate_guard import normalize_code, normalize_name, normalize_phone


def _groups(rows, key_fn):
    buckets = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if key and key[1]:
            buckets[key].append(row)
    return {k: v for k, v in buckets.items() if len(v) > 1}


def report(user_id=None):
    db = SessionLocal()
    try:
        def scoped(model):
            q = db.query(model)
            return q.filter(model.user_id == user_id) if user_id else q

        checks = [
            ("SẢN PHẨM (đang kinh doanh) trùng tên",
             scoped(Product).filter(Product.is_active == True).all(),  # noqa: E712
             lambda r: (r.user_id, normalize_name(r.product_name)),
             lambda r: f"#{r.product_id} '{r.product_name}' ({r.default_unit})"),
            ("KHÁCH HÀNG trùng tên", scoped(Customer).all(),
             lambda r: (r.user_id, normalize_name(r.customer_name)),
             lambda r: f"#{r.customer_id} '{r.customer_name}' {r.phone_number or ''}"),
            ("KHÁCH HÀNG trùng số điện thoại", scoped(Customer).all(),
             lambda r: (r.user_id, normalize_phone(r.phone_number)),
             lambda r: f"#{r.customer_id} '{r.customer_name}' {r.phone_number}"),
            ("NHÀ CUNG CẤP trùng tên", scoped(Supplier).all(),
             lambda r: (r.user_id, normalize_name(r.supplier_name)),
             lambda r: f"#{r.supplier_id} '{r.supplier_name}' {r.phone_number or ''}"),
            ("NHÀ CUNG CẤP trùng số điện thoại", scoped(Supplier).all(),
             lambda r: (r.user_id, normalize_phone(r.phone_number)),
             lambda r: f"#{r.supplier_id} '{r.supplier_name}' {r.phone_number}"),
            ("NHÀ CUNG CẤP trùng mã số thuế", scoped(Supplier).all(),
             lambda r: (r.user_id, normalize_code(r.tax_code)),
             lambda r: f"#{r.supplier_id} '{r.supplier_name}' MST {r.tax_code}"),
        ]

        total = 0
        for title, rows, key_fn, fmt in checks:
            groups = _groups(rows, key_fn)
            if not groups:
                continue
            print(f"\n=== {title}: {len(groups)} nhóm ===")
            for (uid, _), items in sorted(groups.items(), key=lambda kv: kv[0]):
                total += 1
                print(f"  user {uid}: " + " | ".join(fmt(r) for r in items))

        print(f"\nTổng cộng {total} nhóm trùng." if total else "Không có dữ liệu trùng.")
    finally:
        db.close()


if __name__ == "__main__":
    uid = None
    if "--user" in sys.argv:
        uid = int(sys.argv[sys.argv.index("--user") + 1])
    report(uid)
