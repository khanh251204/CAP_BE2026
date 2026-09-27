from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.models.user_model import User
from app.models.product_model import Product, ProductType


class InventoryValidationMixin:
    db: Session
    repo: Any

    def _normalize_payload_items(
        self, user_id: int, payload: Dict[str, Any], is_import: bool = False, **kwargs
    ) -> List[Dict[str, Any]]:
        raw_items = payload.get("items") or payload.get("products") or []

        # Tự đóng gói thành list nếu payload gửi dạng item đơn lẻ
        if not raw_items:
            product_identifier = payload.get("product_name") or payload.get("product") or payload.get("product_id")
            if product_identifier:
                raw_items = [{
                    "product_id": payload.get("product_id"),
                    "product_name": payload.get("product_name") or payload.get("product"),
                    "quantity": payload.get("quantity", 1),
                    "unit": payload.get("unit", ""),
                    "unit_price": payload.get("unit_price") if payload.get("unit_price") is not None else payload.get("price")
                }]

        normalized_items = []
        for item in raw_items:
            p_id = item.get("product_id")
            p_name = item.get("product_name") or item.get("product")

            # 1. Tìm product_id thông qua Repo nếu thiếu ID
            product_obj = None
            if not p_id and p_name:
                p_id = self.repo.get_product_id_by_name(user_id=user_id, name=p_name)
                if not p_id:
                    user_obj = self.db.query(User).filter(User.user_id == user_id).first()
                    raw_bt = getattr(user_obj, "business_type", "") or ""
                    if is_import and str(raw_bt).strip().upper() == "PRODUCER":
                        unit_str = str(item.get("unit") or "đơn vị").strip()
                        raw_price = item.get("unit_price") if item.get("unit_price") is not None else item.get("price")
                        try:
                            init_price = float(raw_price) if raw_price is not None and float(raw_price) > 0 else 0.0
                        except (ValueError, TypeError):
                            init_price = 0.0

                        product_obj = Product(
                            user_id=user_id,
                            product_name=p_name.strip(),
                            default_unit=unit_str,
                            unit_price=str(init_price),
                            product_type=ProductType.RAW_MATERIAL,
                            is_active=True,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        self.db.add(product_obj)
                        self.db.flush()
                        p_id = product_obj.product_id
                    else:
                        raise ValueError(f"Không tìm thấy sản phẩm '{p_name}' trong hệ thống.")

            # 2. Lấy Object Product từ DB để truy xuất giá & đơn vị mặc định
            if not product_obj and p_id:
                product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=p_id)

            # 3. Lấy đơn giá người dùng nhập
            input_price = item.get("unit_price") if item.get("unit_price") is not None else item.get("price")
            final_unit_price = None

            if input_price is not None and float(input_price) > 0:
                final_unit_price = Decimal(str(input_price))
            else:
                if hasattr(self.repo, "get_product_price"):
                    final_unit_price = self.repo.get_product_price(user_id=user_id, product_id=p_id)
                elif product_obj and getattr(product_obj, "unit_price", None) is not None:
                    final_unit_price = Decimal(str(product_obj.unit_price))

            if not final_unit_price or final_unit_price <= 0:
                display_name = p_name or (getattr(product_obj, "name", None) if product_obj else f"ID {p_id}")
                raise ValueError(f"Sản phẩm '{display_name}' chưa có giá trong hệ thống. Vui lòng bổ sung giá.")

            unit = item.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")

            normalized_items.append({
                "product_id": p_id,
                "product_name": p_name or (getattr(product_obj, "name", "") if product_obj else ""),
                "quantity": item.get("quantity", 1),
                "unit": unit,
                "unit_price": final_unit_price
            })

        return normalized_items

    def validate_sale_transaction(
        self,
        user_id: int,
        items: List[Dict[str, Any]],
        user: Optional[User] = None,
        lock_products: bool = False
    ) -> Dict[str, Any]:
        """
        Validate nghiệp vụ bán hàng dựa trên User.business_type và Product.product_type
        """
        if not user:
            user = self.db.query(User).filter(User.user_id == user_id).first()

        raw_business_type = getattr(user, "business_type", None) or "RESELLER"
        business_type = str(raw_business_type).strip().upper()

        validated_items = []
        for item in items:
            product_id = item["product_id"]
            qty = Decimal(str(item["quantity"]))
            product_name = item.get("product_name")

            if lock_products:
                product_obj = (
                    self.db.query(Product)
                    .filter(
                        Product.product_id == product_id,
                        Product.user_id == user_id,
                        Product.is_active == True
                    )
                    .with_for_update()
                    .first()
                )
            else:
                product_obj = (
                    self.db.query(Product)
                    .filter(
                        Product.product_id == product_id,
                        Product.user_id == user_id,
                        Product.is_active == True
                    )
                    .first()
                )

            if not product_obj:
                return {
                    "valid": False,
                    "error_code": "PRODUCT_NOT_FOUND",
                    "message": f"Không tìm thấy sản phẩm '{product_name or product_id}'."
                }

            current_stock = self.repo.get_latest_stock(user_id, product_id)
            actual_name = product_obj.product_name or product_name
            raw_pt = getattr(product_obj, "product_type", "RESALE") or "RESALE"
            product_type = str(raw_pt).strip().upper()

            if business_type == "SERVICE":
                validated_items.append({
                    "product_id": product_id,
                    "product_obj": product_obj,
                    "product_name": actual_name,
                    "quantity": qty,
                    "product_type": product_type,
                    "current_stock": current_stock,
                    "can_deduct_stock": False
                })
                continue

            if business_type == "PRODUCER":
                if product_type == "RAW_MATERIAL":
                    return {
                        "valid": False,
                        "error_code": "CANNOT_SELL_RAW_MATERIAL",
                        "message": f"Sản phẩm '{actual_name}' là nguyên liệu sản xuất (RAW_MATERIAL), không thể bán trực tiếp dưới dạng thành phẩm."
                    }
                else:
                    can_deduct = (current_stock >= qty)
                    validated_items.append({
                        "product_id": product_id,
                        "product_obj": product_obj,
                        "product_name": actual_name,
                        "quantity": qty,
                        "product_type": product_type,
                        "current_stock": current_stock,
                        "can_deduct_stock": can_deduct
                    })
                    continue

            if current_stock < qty:
                return {
                    "valid": False,
                    "error_code": "INSUFFICIENT_STOCK",
                    "message": f"Sản phẩm '{actual_name}' không đủ tồn kho (Tồn: {current_stock}, Yêu cầu: {qty})"
                }

            validated_items.append({
                "product_id": product_id,
                "product_obj": product_obj,
                "product_name": actual_name,
                "quantity": qty,
                "product_type": product_type,
                "current_stock": current_stock,
                "can_deduct_stock": True
            })

        return {
            "valid": True,
            "business_type": business_type,
            "items": validated_items
        }

    def check_stock(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name")

            if not product_id and product_name:
                product_id = self.repo.get_product_id_by_name(
                    user_id=user_id,
                    name=product_name
                )

            if not product_id:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Không tìm thấy sản phẩm '{product_name}'."
                }

            stock = self.repo.get_latest_stock(
                user_id=user_id,
                product_id=product_id
            )

            product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=product_id)
            
            unit_price = 0.0
            default_unit = ""
            if product_obj:
                if hasattr(product_obj, "unit_price") and product_obj.unit_price is not None:
                    unit_price = float(product_obj.unit_price)
                elif hasattr(product_obj, "price") and product_obj.price is not None:
                    unit_price = float(product_obj.price)

                if hasattr(product_obj, "default_unit") and product_obj.default_unit is not None:
                    default_unit = str(product_obj.default_unit)
                elif hasattr(product_obj, "unit") and product_obj.unit is not None:
                    default_unit = str(product_obj.unit)
            
            actual_product_name = product_name or (getattr(product_obj, "name", "") if product_obj else "")

            user = self.db.query(User).filter(User.user_id == user_id).first()
            raw_business_type = getattr(user, "business_type", None) or "RESELLER"
            business_type = str(raw_business_type).strip().upper()
            raw_pt = getattr(product_obj, "product_type", "RESALE") if product_obj else "RESALE"
            product_type = str(raw_pt or "RESALE").strip().upper()

            return {
                "status": "success",
                "success": True,
                "message": f"Sản phẩm '{actual_product_name}' còn {stock}.",
                "product_id": product_id,
                "product_name": actual_product_name,
                "product_type": product_type,
                "business_type": business_type,
                "quantity": float(stock),
                "unit_price": unit_price,
                "default_unit": default_unit
            }

        except Exception as e:
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi kiểm tra tồn kho: {str(e)}"
            }
