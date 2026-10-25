"""
Chặn tạo trùng Sản phẩm / Nhà cung cấp / Khách hàng trong phạm vi một user (multi-tenant).

Quy tắc trùng (so sánh sau khi chuẩn hóa, độc lập với collation của DB):
- Tên: bỏ khoảng trắng thừa và ký tự vô hình, không phân biệt hoa/thường, kiểu gõ NFC/NFD
  hay vị trí đặt dấu thanh ("hoà" == "hòa"), nhưng GIỮ NGUYÊN dấu tiếng Việt
  ("Coca  cola" == "coca cola", nhưng "Bơ" != "Bò").
- Số điện thoại (khách hàng, nhà cung cấp): chỉ so phần chữ số, "+84"/"84" quy về "0".
- Mã số thuế (nhà cung cấp): bỏ khoảng trắng, không phân biệt hoa/thường.
- Sản phẩm: chỉ so với sản phẩm đang kinh doanh (is_active); sản phẩm đã xóa mềm giữ lịch sử.

Chống race condition: khóa dòng User (SELECT ... FOR UPDATE) trước khi kiểm tra, nên hai
request tạo cùng lúc của một user được xử lý tuần tự; khóa nhả khi commit/rollback.
"""
import re
import unicodedata
from typing import Iterable, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.customer_model import Customer
from app.models.product_model import Product
from app.models.supplier_model import Supplier
from app.models.user_model import User


# =============================================
# CHUẨN HÓA
# =============================================

# 5 dấu thanh tiếng Việt (dạng tổ hợp): huyền, sắc, ngã, hỏi, nặng.
# Không gồm dấu mũ (â ê ô), trăng (ă), móc (ơ ư) vì đó là chữ cái khác nhau.
_TONE_MARKS = {"̀", "́", "̃", "̉", "̣"}


def _strip_invisible(text: str) -> str:
    """Bỏ ký tự định dạng vô hình (zero-width space/joiner, BOM...) thường dính khi copy-paste."""
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def _tone_key(word: str) -> str:
    """
    Khóa so sánh của một âm tiết, không phụ thuộc VỊ TRÍ đặt dấu thanh:
    "hoà" (kiểu cũ) và "hòa" (kiểu mới) -> cùng khóa; "bò" và "bơ" vẫn khác nhau.
    """
    decomposed = unicodedata.normalize("NFD", word)
    tones = sorted(ch for ch in decomposed if ch in _TONE_MARKS)
    base = unicodedata.normalize("NFC", "".join(ch for ch in decomposed if ch not in _TONE_MARKS))
    return base + ("|" + "".join(tones) if tones else "")


def normalize_name(value: Optional[str]) -> str:
    """
    Khóa so trùng tên: không phân biệt hoa/thường, khoảng trắng thừa, ký tự vô hình,
    kiểu gõ dựng sẵn/tổ hợp (NFC/NFD) và vị trí đặt dấu thanh — nhưng GIỮ phân biệt dấu.
    """
    text = _strip_invisible(unicodedata.normalize("NFC", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return " ".join(_tone_key(w) for w in text.split(" ")) if text else ""


def clean_name(value: Optional[str]) -> str:
    """Tên để lưu: bỏ khoảng trắng thừa, ký tự vô hình; giữ nguyên chữ hoa/thường người dùng nhập."""
    text = _strip_invisible(unicodedata.normalize("NFC", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def normalize_phone(value: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return None
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits


def normalize_code(value: Optional[str]) -> Optional[str]:
    code = re.sub(r"\s+", "", str(value or "")).upper()
    return code or None


def lock_user_scope(db: Session, user_id: int) -> None:
    """Tuần tự hóa các thao tác tạo/sửa danh mục của cùng một user."""
    db.query(User.user_id).filter(User.user_id == user_id).with_for_update().first()


def _conflict(message: str) -> HTTPException:
    # Trùng với bản ghi đã có -> 409 Conflict (chuẩn REST)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


# =============================================
# SẢN PHẨM
# =============================================

def find_duplicate_product(
    db: Session, user_id: int, name: str, exclude_id: Optional[int] = None
) -> Optional[Product]:
    key = normalize_name(name)
    if not key:
        return None
    query = db.query(Product).filter(Product.user_id == user_id, Product.is_active == True)  # noqa: E712
    if exclude_id is not None:
        query = query.filter(Product.product_id != exclude_id)
    for product in query.all():
        if normalize_name(product.product_name) == key:
            return product
    return None


def ensure_unique_product(
    db: Session, user_id: int, name: str, exclude_id: Optional[int] = None, lock: bool = True
) -> None:
    if lock:
        lock_user_scope(db, user_id)
    dup = find_duplicate_product(db, user_id, name, exclude_id)
    if dup:
        raise _conflict(f"Sản phẩm '{dup.product_name}' đã tồn tại (ID: {dup.product_id})")


# =============================================
# KHÁCH HÀNG / NHÀ CUNG CẤP
# =============================================

def _find_party(
    rows: Iterable, name_attr: str, id_attr: str, name: Optional[str], phone: Optional[str],
    tax_code: Optional[str] = None,
) -> Tuple[Optional[object], Optional[str]]:
    name_key = normalize_name(name) if name is not None else None
    phone_key = normalize_phone(phone)
    tax_key = normalize_code(tax_code)
    for row in rows:
        if name_key and normalize_name(getattr(row, name_attr)) == name_key:
            return row, "name"
        if phone_key and normalize_phone(getattr(row, "phone_number", None)) == phone_key:
            return row, "phone"
        if tax_key and normalize_code(getattr(row, "tax_code", None)) == tax_key:
            return row, "tax_code"
    return None, None


def find_duplicate_customer(
    db: Session, user_id: int, name: Optional[str] = None, phone: Optional[str] = None,
    exclude_id: Optional[int] = None,
) -> Tuple[Optional[Customer], Optional[str]]:
    query = db.query(Customer).filter(Customer.user_id == user_id)
    if exclude_id is not None:
        query = query.filter(Customer.customer_id != exclude_id)
    return _find_party(query.all(), "customer_name", "customer_id", name, phone)


def ensure_unique_customer(
    db: Session, user_id: int, name: Optional[str] = None, phone: Optional[str] = None,
    exclude_id: Optional[int] = None, lock: bool = True,
) -> None:
    if lock:
        lock_user_scope(db, user_id)
    dup, field = find_duplicate_customer(db, user_id, name, phone, exclude_id)
    if dup:
        if field == "phone":
            raise _conflict(
                f"Số điện thoại {dup.phone_number} đã được dùng cho khách hàng '{dup.customer_name}' (ID: {dup.customer_id})"
            )
        raise _conflict(f"Khách hàng '{dup.customer_name}' đã tồn tại (ID: {dup.customer_id})")


def find_duplicate_supplier(
    db: Session, user_id: int, name: Optional[str] = None, phone: Optional[str] = None,
    tax_code: Optional[str] = None, exclude_id: Optional[int] = None,
) -> Tuple[Optional[Supplier], Optional[str]]:
    query = db.query(Supplier).filter(Supplier.user_id == user_id)
    if exclude_id is not None:
        query = query.filter(Supplier.supplier_id != exclude_id)
    return _find_party(query.all(), "supplier_name", "supplier_id", name, phone, tax_code)


def ensure_unique_supplier(
    db: Session, user_id: int, name: Optional[str] = None, phone: Optional[str] = None,
    tax_code: Optional[str] = None, exclude_id: Optional[int] = None, lock: bool = True,
) -> None:
    if lock:
        lock_user_scope(db, user_id)
    dup, field = find_duplicate_supplier(db, user_id, name, phone, tax_code, exclude_id)
    if dup:
        if field == "phone":
            raise _conflict(
                f"Số điện thoại {dup.phone_number} đã được dùng cho nhà cung cấp '{dup.supplier_name}' (ID: {dup.supplier_id})"
            )
        if field == "tax_code":
            raise _conflict(
                f"Mã số thuế {dup.tax_code} đã được dùng cho nhà cung cấp '{dup.supplier_name}' (ID: {dup.supplier_id})"
            )
        raise _conflict(f"Nhà cung cấp '{dup.supplier_name}' đã tồn tại (ID: {dup.supplier_id})")


def get_or_create_customer_by_name(db: Session, user_id: int, name: str) -> Customer:
    """Dùng cho luồng tự tạo khách hàng khi ghi giao dịch: tái sử dụng bản ghi đã có thay vì tạo trùng."""
    from datetime import datetime

    lock_user_scope(db, user_id)
    existing, _ = find_duplicate_customer(db, user_id, name=name)
    if existing:
        return existing
    now = datetime.now()
    customer = Customer(user_id=user_id, customer_name=clean_name(name), created_at=now, updated_at=now)
    db.add(customer)
    db.flush()
    return customer


def get_or_create_supplier_by_name(db: Session, user_id: int, name: str, **fields) -> Supplier:
    """Dùng cho luồng tự tạo nhà cung cấp khi ghi giao dịch: tái sử dụng bản ghi đã có thay vì tạo trùng."""
    from datetime import datetime

    lock_user_scope(db, user_id)
    existing, _ = find_duplicate_supplier(db, user_id, name=name)
    if existing:
        return existing
    now = datetime.now()
    supplier = Supplier(user_id=user_id, supplier_name=clean_name(name), created_at=now, updated_at=now, **fields)
    db.add(supplier)
    db.flush()
    return supplier
