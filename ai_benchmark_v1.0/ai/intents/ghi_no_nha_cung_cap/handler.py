from typing import Any
from datetime import datetime

from app.configs.database import get_db_session
from app.models.supplier_model import Supplier
from .validator import validate
from .payload import build_payload


class GhiNoNhaCungCapHandler:
    """
    Business workflow cho intent: ghi_no_nha_cung_cap (ncc_ghi_no)
    Xử lý:
    - Tìm hoặc tự tạo Supplier trong DB nếu chưa có theo supplier_name.
    - Validate số tiền (hoặc tính từ sản phẩm x đơn giá x số lượng).
    - Trả về waiting_confirmation để người dùng xác nhận.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "ghi_no_nha_cung_cap"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        supplier_name = entities.get("supplier") or entities.get("supplier_name")
        if not supplier_name:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["supplier"],
                "message": "Thiếu thông tin nhà cung cấp cần ghi nợ"
            }

        product_name = entities.get("product")
        raw_qty = entities.get("quantity")
        raw_unit_price = entities.get("price") or entities.get("unit_price")
        raw_amount = (
            entities.get("original_amount")
            or entities.get("amount")
            or entities.get("total_price")
        )
        unit = entities.get("unit")

        try:
            qty = float(raw_qty) if raw_qty is not None else 1.0
        except (ValueError, TypeError):
            qty = 1.0

        unit_price = None
        if raw_unit_price is not None:
            try:
                unit_price = float(raw_unit_price)
            except (ValueError, TypeError):
                unit_price = None

        if raw_amount is not None:
            try:
                original_amount = float(raw_amount)
            except (ValueError, TypeError):
                original_amount = None
        elif product_name and unit_price is not None and unit_price > 0 and raw_qty is not None:
            original_amount = unit_price * qty
        elif unit_price is not None and unit_price > 0:
            original_amount = unit_price
        else:
            original_amount = None

        if original_amount is None or original_amount <= 0:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["price"],
                "message": "Thiếu thông tin số tiền nợ (hoặc sản phẩm và đơn giá)"
            }

        supplier_id = entities.get("supplier_id")
        if not supplier_id:
            db = get_db_session()
            try:
                db_supplier = (
                    db.query(Supplier)
                    .filter(
                        Supplier.user_id == user_id,
                        Supplier.supplier_name.ilike(f"%{supplier_name}%")
                    )
                    .first()
                )
                if not db_supplier:
                    return {
                        "success": False,
                        "status": "error",
                        "code": "SUPPLIER_NOT_FOUND",
                        "intent": intent,
                        "supplier_name": supplier_name,
                        "message": f"Không tìm thấy nhà cung cấp '{supplier_name}' trong hệ thống. Vui lòng tạo nhà cung cấp trước."
                    }
                supplier_id = db_supplier.supplier_id
                if hasattr(db_supplier, "supplier_name") and db_supplier.supplier_name:
                    supplier_name = db_supplier.supplier_name
            finally:
                db.close()

        payload = build_payload(entities=entities, text=text)
        payload["supplier_id"] = supplier_id
        payload["supplier_name"] = supplier_name
        payload["original_amount"] = original_amount
        payload["amount"] = original_amount
        if product_name:
            payload["product_name"] = product_name
        if unit_price is not None:
            payload["unit_price"] = unit_price
        payload["quantity"] = qty
        if unit:
            payload["unit"] = unit

        qty_str = f"{int(qty) if qty.is_integer() else qty}"
        detail_str = ""
        if product_name and unit_price is not None:
            unit_str = f" {unit}" if unit else ""
            detail_str = f" ({qty_str}{unit_str} {product_name} x {unit_price:,.0f}đ)"

        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "ghi_no_nha_cung_cap",
            "payload": payload,
            "message": (
                f"Bạn có chắc muốn ghi nợ cho nhà cung cấp {supplier_name} "
                f"số tiền {original_amount:,.0f}đ{detail_str} không?"
            )
        }
