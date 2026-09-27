from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.orm import Session


class InventoryMovementMixin:
    db: Session
    repo: Any

    def nhap_kho(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ nhập kho đơn thuần (Inventory IN).
        """
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name") or payload.get("product")
            quantity_raw = payload.get("quantity")

            if quantity_raw is None or quantity_raw == "":
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["quantity"],
                    "message": "Thiếu thông tin số lượng cần nhập kho."
                }

            try:
                qty = Decimal(str(quantity_raw))
                if qty <= 0:
                    return {
                        "status": "error",
                        "success": False,
                        "message": "Số lượng nhập kho phải lớn hơn 0."
                    }
            except Exception:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Số lượng không hợp lệ: {quantity_raw}"
                }

            if not product_id and product_name:
                product_id = self.repo.get_product_id_by_name(user_id=user_id, name=str(product_name))
                if not product_id:
                    return {
                        "status": "error",
                        "success": False,
                        "missing_fields": ["product"],
                        "message": f"Không tìm thấy sản phẩm '{product_name}' trong hệ thống."
                    }
            elif not product_id and not product_name:
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["product"],
                    "message": "Thiếu thông tin sản phẩm cần nhập kho."
                }

            product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=product_id)
            unit = payload.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")
            actual_product_name = product_name or (getattr(product_obj, "product_name", "") if product_obj else f"ID {product_id}")

            qty_before = self.repo.get_latest_stock(user_id, product_id)
            qty_after = qty_before + qty

            inv_tx = self.repo.create_inventory_transaction(
                user_id=user_id,
                product_id=product_id,
                transaction_id=None,
                type="IN",
                quantity=qty,
                unit=unit,
                quantity_before=qty_before,
                quantity_after=qty_after,
                note=payload.get("note") or payload.get("input_text") or "Nhập kho",
            )

            self.db.commit()
            self.db.refresh(inv_tx)

            return {
                "status": "success",
                "success": True,
                "message": f"Nhập kho thành công {qty} {unit} {actual_product_name}.",
                "inventory_transaction_id": inv_tx.inventory_transaction_id,
                "product_id": product_id,
                "product_name": actual_product_name,
                "quantity": float(qty),
                "unit": unit,
                "quantity_before": float(qty_before),
                "quantity_after": float(qty_after),
                "inventory_type": "IN"
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi xử lý nhập kho: {str(e)}"
            }

    def xuat_kho(
        self,
        user_id: int,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ xuất kho đơn thuần (Inventory OUT).
        """
        try:
            product_id = payload.get("product_id")
            product_name = payload.get("product_name") or payload.get("product")
            quantity_raw = payload.get("quantity")

            if quantity_raw is None or quantity_raw == "":
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["quantity"],
                    "message": "Thiếu thông tin số lượng cần xuất kho."
                }

            try:
                qty = Decimal(str(quantity_raw))
                if qty <= 0:
                    return {
                        "status": "error",
                        "success": False,
                        "message": "Số lượng xuất kho phải lớn hơn 0."
                    }
            except Exception:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Số lượng không hợp lệ: {quantity_raw}"
                }

            if not product_id and product_name:
                product_id = self.repo.get_product_id_by_name(user_id=user_id, name=str(product_name))
                if not product_id:
                    return {
                        "status": "error",
                        "success": False,
                        "missing_fields": ["product"],
                        "message": f"Không tìm thấy sản phẩm '{product_name}' trong hệ thống."
                    }
            elif not product_id and not product_name:
                return {
                    "status": "error",
                    "success": False,
                    "missing_fields": ["product"],
                    "message": "Thiếu thông tin sản phẩm cần xuất kho."
                }

            product_obj = self.repo.get_product_by_id(user_id=user_id, product_id=product_id)
            unit = payload.get("unit") or (getattr(product_obj, "default_unit", "") if product_obj else "")
            actual_product_name = product_name or (getattr(product_obj, "product_name", "") if product_obj else f"ID {product_id}")

            qty_before = self.repo.get_latest_stock(user_id, product_id)
            if qty_before < qty:
                return {
                    "status": "error",
                    "success": False,
                    "message": f"Sản phẩm '{actual_product_name}' không đủ tồn kho (Tồn: {qty_before}, Yêu cầu: {qty})"
                }

            qty_after = qty_before - qty

            inv_tx = self.repo.create_inventory_transaction(
                user_id=user_id,
                product_id=product_id,
                transaction_id=None,
                type="OUT",
                quantity=qty,
                unit=unit,
                quantity_before=qty_before,
                quantity_after=qty_after,
                note=payload.get("note") or payload.get("input_text") or "Xuất kho",
            )

            self.db.commit()
            self.db.refresh(inv_tx)

            return {
                "status": "success",
                "success": True,
                "message": f"Xuất kho thành công {qty} {unit} {actual_product_name}.",
                "inventory_transaction_id": inv_tx.inventory_transaction_id,
                "product_id": product_id,
                "product_name": actual_product_name,
                "quantity": float(qty),
                "unit": unit,
                "quantity_before": float(qty_before),
                "quantity_after": float(qty_after),
                "inventory_type": "OUT"
            }

        except Exception as e:
            self.db.rollback()
            return {
                "status": "error",
                "success": False,
                "message": f"Lỗi xử lý xuất kho: {str(e)}"
            }
