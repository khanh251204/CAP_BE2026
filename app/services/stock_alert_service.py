import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.models.user_model import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

DEFAULT_STOCK_ALERT_COOLDOWN_HOURS = 12


class StockAlertService:
    """
    Dịch vụ phát hiện và gửi thông báo cho:
    1. Mặt hàng đã bán hết (Tồn kho <= 0): OUT_OF_STOCK
    2. Mặt hàng sắp hết (0 < Tồn kho <= min_quantity): LOW_STOCK
    """

    @classmethod
    def _is_cooldown_active(
        cls,
        user_id: int | str,
        product_id: int,
        alert_type: str,
        cooldown_hours: int = DEFAULT_STOCK_ALERT_COOLDOWN_HOURS
    ) -> bool:
        """
        Kiểm tra cooldown tránh gửi spam thông báo lặp lại cho cùng 1 sản phẩm.
        Quy tắc:
        - Nếu cùng alert_type trong vòng cooldown_hours -> Bỏ qua (cooldown active).
        - Ngoại lệ: Nếu trước đó là LOW_STOCK mà hiện tại thành OUT_OF_STOCK -> Không áp dụng cooldown (cho phép gửi ngay).
        """
        try:
            from app.configs.firebase import db as firestore_db
            doc_id = f"{user_id}_{product_id}"
            doc_ref = firestore_db.collection("stock_alert_cooldown").document(doc_id)
            doc = doc_ref.get()

            if not doc.exists:
                return False

            data = doc.to_dict() or {}
            last_alert_type = data.get("alertType")
            last_alert_at = data.get("lastAlertAt")

            # Nếu trước đó chỉ báo LOW_STOCK mà giờ hàng hết hẳn (OUT_OF_STOCK) -> ưu tiên gửi ngay
            if last_alert_type == "LOW_STOCK" and alert_type == "OUT_OF_STOCK":
                return False

            if last_alert_at:
                dt = last_alert_at.to_datetime() if hasattr(last_alert_at, "to_datetime") else last_alert_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)

                cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
                if dt >= cutoff:
                    return True

            return False
        except Exception as e:
            logger.debug(f"[StockAlert] Không thể kiểm tra cooldown qua Firestore: {e}")
            return False

    @classmethod
    def _update_cooldown(
        cls,
        user_id: int | str,
        product_id: int,
        alert_type: str,
        current_stock: float
    ):
        """
        Ghi nhận mốc thời gian vừa gửi cảnh báo vào Firestore.
        """
        try:
            from app.configs.firebase import db as firestore_db
            from firebase_admin import firestore
            doc_id = f"{user_id}_{product_id}"
            firestore_db.collection("stock_alert_cooldown").document(doc_id).set({
                "userId": str(user_id),
                "productId": int(product_id),
                "alertType": alert_type,
                "stock": float(current_stock),
                "lastAlertAt": firestore.SERVER_TIMESTAMP
            }, merge=True)
        except Exception as e:
            logger.debug(f"[StockAlert] Không thể lưu cooldown Firestore: {e}")

    @classmethod
    def check_and_notify_stock(
        cls,
        db: Session,
        user_id: int,
        product_id: int,
        current_stock: Optional[Decimal | float] = None,
        cooldown_hours: int = DEFAULT_STOCK_ALERT_COOLDOWN_HOURS
    ) -> Optional[Dict[str, Any]]:
        """
        Kiểm tra tồn kho và tạo thông báo nếu hết hàng hoặc dưới ngưỡng min_quantity:
        - Tồn kho <= 0 -> OUT_OF_STOCK
        - 0 < Tồn kho <= min_quantity (với min_quantity > 0) -> LOW_STOCK
        """
        try:
            # 1. Truy vấn sản phẩm (Multi-tenancy)
            product = (
                db.query(Product)
                .filter(
                    Product.user_id == user_id,
                    Product.product_id == product_id,
                    Product.is_active == True
                )
                .first()
            )
            if not product:
                return None

            # Bỏ qua nếu mô hình kinh doanh là SERVICE
            user = db.query(User).filter(User.user_id == user_id).first()
            if user and getattr(user, "business_type", None) == "SERVICE":
                return None

            # 2. Xác định số tồn kho hiện tại
            if current_stock is None:
                latest_inv = (
                    db.query(InventoryTransaction)
                    .filter(
                        InventoryTransaction.user_id == user_id,
                        InventoryTransaction.product_id == product_id
                    )
                    .order_by(InventoryTransaction.inventory_transaction_id.desc())
                    .first()
                )
                stock_dec = Decimal(str(latest_inv.quantity_after)) if latest_inv else Decimal("0.0")
            else:
                stock_dec = Decimal(str(current_stock))

            min_qty = Decimal(str(product.min_quantity)) if product.min_quantity is not None else Decimal("0.0")
            unit_display = product.default_unit or "sản phẩm"
            stock_float = float(stock_dec)
            min_float = float(min_qty)

            # 3. Phân loại cảnh báo
            alert_type: Optional[str] = None
            title: str = ""
            description: str = ""
            icon: str = "alert-circle"
            icon_color: str = "#EF4444"
            border_color: str = "#DC2626"

            if stock_dec <= Decimal("0.0"):
                alert_type = "OUT_OF_STOCK"
                title = f"Hết hàng: {product.product_name} ⚠️"
                description = (
                    f"Mặt hàng '{product.product_name}' đã hết hàng trong kho "
                    f"(Tồn: {stock_float:g} {unit_display}). Vui lòng nhập thêm hàng!"
                )
                icon = "alert-circle"
                icon_color = "#EF4444"
                border_color = "#DC2626"
            elif min_qty > Decimal("0.0") and stock_dec <= min_qty:
                alert_type = "LOW_STOCK"
                title = f"Cảnh báo tồn kho thấp: {product.product_name} ⚠️"
                description = (
                    f"Mặt hàng '{product.product_name}' sắp hết "
                    f"(Tồn kho: {stock_float:g} {unit_display} <= ngưỡng tối thiểu {min_float:g} {unit_display}). "
                    f"Hãy chuẩn bị nhập thêm hàng."
                )
                icon = "alert-triangle"
                icon_color = "#F59E0B"
                border_color = "#D97706"
            else:
                # Tồn kho an toàn > min_quantity -> không gửi cảnh báo
                return None

            # 4. Kiểm tra cooldown chống spam
            if cls._is_cooldown_active(user_id, product_id, alert_type, cooldown_hours):
                logger.info(
                    f"[StockAlert] Bỏ qua gửi thông báo '{alert_type}' cho #{product_id} "
                    f"({product.product_name}) do đang trong thời gian cooldown."
                )
                return None

            # 5. Tạo thông báo (lưu Firestore & đẩy FCM Push)
            notif_data = {
                "userId": str(user_id),
                "title": title,
                "description": description,
                "notificationType": alert_type,
                "icon": icon,
                "iconColor": icon_color,
                "borderColor": border_color,
                "isRead": False,
                "productId": product.product_id,
                "productName": product.product_name,
                "currentStock": stock_float,
                "minQuantity": min_float,
                "unit": unit_display
            }

            result = NotificationService.create_notification(notif_data)

            # Cập nhật cooldown
            cls._update_cooldown(user_id, product_id, alert_type, stock_float)

            logger.info(
                f"[StockAlert] Đã gửi thông báo '{alert_type}' cho user {user_id}: "
                f"Sản phẩm #{product_id} '{product.product_name}' (Tồn: {stock_float:g}/{min_float:g})"
            )
            return result

        except Exception as e:
            logger.error(f"[StockAlert] Lỗi khi xử lý cảnh báo tồn kho cho #{product_id}: {e}", exc_info=True)
            return None

    @classmethod
    def get_stock_alerts(
        cls,
        db: Session,
        user_id: int,
        alert_type: Optional[str] = "ALL"
    ) -> Dict[str, Any]:
        """
        Lấy danh sách các mặt hàng hết hàng hoặc dưới ngưỡng min_quantity:
        - alert_type: 'ALL' | 'OUT_OF_STOCK' | 'LOW_STOCK'
        """
        from app.repositories import product_repository as repo

        products_with_stock = repo.get_products_with_stock(db, user_id)
        out_of_stock_list: List[Dict[str, Any]] = []
        low_stock_list: List[Dict[str, Any]] = []

        for p in products_with_stock:
            # Chỉ xét sản phẩm đang active
            if not p.get("is_active", True):
                continue

            stock = float(p.get("stock_quantity") or 0.0)
            min_q = float(p.get("min_quantity") or 0.0)
            unit = p.get("default_unit") or ""
            name = p.get("name") or ""

            item_info = {
                "product_id": p.get("product_id"),
                "product_name": name,
                "product_type": p.get("product_type"),
                "default_unit": unit,
                "unit_price": float(p.get("unit_price") or 0.0),
                "min_quantity": min_q,
                "current_stock": stock,
                "total_imported": float(p.get("total_imported") or 0.0),
                "total_sold": float(p.get("total_sold") or 0.0)
            }

            if stock <= 0:
                item_info["alert_type"] = "OUT_OF_STOCK"
                item_info["alert_message"] = (
                    f"Sản phẩm '{name}' đã hết hàng trong kho (Tồn: {stock:g} {unit})."
                )
                item_info["severity"] = "HIGH"
                out_of_stock_list.append(item_info)
            elif min_q > 0 and stock <= min_q:
                item_info["alert_type"] = "LOW_STOCK"
                item_info["alert_message"] = (
                    f"Sản phẩm '{name}' sắp hết hàng (Tồn: {stock:g} {unit} <= tối thiểu: {min_q:g} {unit})."
                )
                item_info["severity"] = "MEDIUM"
                low_stock_list.append(item_info)

        # Lọc danh sách theo filter
        filter_type = (alert_type or "ALL").strip().upper()
        if filter_type == "OUT_OF_STOCK":
            alerts = out_of_stock_list
        elif filter_type == "LOW_STOCK":
            alerts = low_stock_list
        else:
            alerts = out_of_stock_list + low_stock_list

        return {
            "success": True,
            "summary": {
                "total_alerts": len(alerts),
                "total_out_of_stock": len(out_of_stock_list),
                "total_low_stock": len(low_stock_list),
            },
            "data": alerts
        }
