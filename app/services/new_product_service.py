"""
Tự thêm sản phẩm mới khi giao dịch (giọng nói / MCP) nhắc tới sản phẩm chưa có trong danh mục.

Luồng 2 pha (AGENTS.md):
1. Bản nháp (handler): không tìm thấy sản phẩm -> đính kèm payload["new_product"] (đơn vị, giá, loại)
   và báo trong câu xác nhận "sản phẩm mới, sẽ được thêm vào danh mục".
2. Xác nhận (InventoryService): tạo sản phẩm trong CÙNG DB session với giao dịch (lỗi là rollback cả hai),
   sau khi commit thì gửi thông báo "Đã thêm sản phẩm mới" cho người dùng (Firestore + push FCM).

Quy tắc được tạo sản phẩm mới:
- Nhập hàng / mua hàng / nhập kho: mọi loại hình kinh doanh.
- Bán hàng: chỉ PRODUCER (làm theo yêu cầu, tồn kho có thể = 0) và SERVICE (dịch vụ, không cần kho).
  RESELLER không thể bán hàng chưa từng nhập (tồn kho = 0) -> báo nhập hàng trước.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.product_model import Product
from app.services.duplicate_guard import clean_name, find_duplicate_product, lock_user_scope

logger = logging.getLogger(__name__)

NEW_PRODUCT_KEY = "new_product"

FLOW_PURCHASE = "purchase"   # mua_hang / nhap_hang
FLOW_STOCK_IN = "stock_in"   # nhap_kho
FLOW_SALE = "sale"           # ban_hang


def can_create_on_flow(flow: str, business_type: Optional[str]) -> bool:
    bt = str(business_type or "RESELLER").strip().upper()
    if flow == FLOW_SALE:
        return bt in ("PRODUCER", "SERVICE")
    return True


def default_product_type(flow: str, business_type: Optional[str]) -> str:
    bt = str(business_type or "RESELLER").strip().upper()
    if bt == "PRODUCER":
        # Quán/xưởng: hàng nhập về là nguyên liệu, hàng bán ra là thành phẩm
        return "FINISHED_GOOD" if flow == FLOW_SALE else "RAW_MATERIAL"
    return "RESALE"


PRODUCT_TYPE_LABEL = {
    "RESALE": "hàng bán lại",
    "RAW_MATERIAL": "nguyên liệu",
    "FINISHED_GOOD": "thành phẩm",
}


def _positive_price(value: Any) -> Optional[float]:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def build_spec(
    name: str,
    unit: Optional[str],
    sale_price: Any,
    product_type: str,
    price_from_item: bool = False,
) -> Dict[str, Any]:
    """
    Thông tin sản phẩm mới đính kèm vào payload bản nháp.
    sale_price: GIÁ BÁN của sản phẩm (None nếu chưa biết, ví dụ khi nhập hàng chỉ biết giá nhập).
    price_from_item: lấy đơn giá trên dòng hàng làm giá bán (đúng với luồng bán hàng).
    """
    return {
        "product_name": clean_name(name),
        "default_unit": clean_name(unit) or None,
        "unit_price": _positive_price(sale_price),
        "product_type": product_type,
        "price_from_item": price_from_item,
    }


def describe(spec: Dict[str, Any]) -> str:
    """Mô tả ngắn để chèn vào câu xác nhận / thông báo."""
    label = PRODUCT_TYPE_LABEL.get(spec.get("product_type"), "sản phẩm")
    price = spec.get("unit_price")
    price_text = f", giá {price:,.0f}đ/{spec.get('default_unit') or ''}" if price else ", chưa có giá bán"
    return f"'{spec['product_name']}' ({label}{price_text})"


def get_or_create_from_spec(
    db: Session,
    user_id: int,
    product_name: str,
    spec: Dict[str, Any],
    unit: Optional[str] = None,
    unit_price: Any = None,
) -> Tuple[Product, bool]:
    """
    Tạo sản phẩm theo spec (chưa commit — commit cùng giao dịch).
    Tên lấy theo dòng hàng thực tế (người dùng có thể đã sửa tên trước khi xác nhận);
    đơn vị / giá trên dòng hàng được ưu tiên hơn spec.
    Trả về (product, created). Nếu trong lúc chờ xác nhận đã có sản phẩm trùng tên thì dùng lại.
    """
    name = clean_name(product_name or spec.get("product_name"))
    if not name:
        raise ValueError("Thiếu tên sản phẩm mới.")
    if len(name) > 255:
        raise ValueError("Tên sản phẩm tối đa 255 ký tự.")

    lock_user_scope(db, user_id)
    existing = find_duplicate_product(db, user_id, name)
    if existing:
        return existing, False

    # Chỉ luồng bán hàng mới lấy đơn giá trên dòng hàng làm giá bán (nhập hàng thì đó là giá vốn)
    item_price = _positive_price(unit_price) if spec.get("price_from_item") else None
    price = item_price or spec.get("unit_price")
    now = datetime.now()
    product = Product(
        user_id=user_id,
        product_name=name,
        default_unit=clean_name(unit) or spec.get("default_unit") or "cái",
        unit_price=str(price) if price else None,
        min_quantity=0,
        product_type=spec.get("product_type") or "RESALE",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    db.flush()
    return product, True


def product_summary(product: Product) -> Dict[str, Any]:
    price = _positive_price(product.unit_price)
    return {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "default_unit": product.default_unit,
        "unit_price": price,
        "product_type": str(getattr(product.product_type, "value", product.product_type)),
    }


def notification_message(products: List[Dict[str, Any]]) -> str:
    return "Đã thêm sản phẩm mới vào danh mục: " + ", ".join(describe(p) for p in products) + "."


def notify_new_products(user_id: int, products: List[Dict[str, Any]]) -> None:
    """Gửi thông báo (Firestore + push) sau khi giao dịch đã commit. Lỗi gửi không ảnh hưởng giao dịch."""
    if not products:
        return
    try:
        from app.services.notification_service import NotificationService

        missing_price = [p["product_name"] for p in products if not p.get("unit_price")]
        description = notification_message(products)
        if missing_price:
            description += " Hãy cập nhật giá bán cho: " + ", ".join(missing_price) + "."
        NotificationService.create_notification({
            "userId": str(user_id),
            "title": "Đã thêm sản phẩm mới 🆕",
            "description": description,
            "notificationType": "NEW_PRODUCT",
            "icon": "package-plus",
            "iconColor": "#FFFFFF",
            "borderColor": "#2563EB",
            "isRead": False,
            "productIds": [p["product_id"] for p in products],
        })
    except Exception as e:
        logger.warning(f"[NewProduct] Không gửi được thông báo sản phẩm mới cho user {user_id}: {e}")
