from typing import Any
from datetime import datetime

from app.configs.database import get_db_session
from app.models.supplier_model import Supplier
from app.repositories.inventory.inventory_lookup_repo import AmbiguousMatchError, InventoryLookupRepository
from app.services.new_supplier_service import NEW_SUPPLIER_KEY, new_supplier_question
from app.ai.intents.missing_info import first_value, is_not_positive
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
                "message": "Bạn chưa nói tên nhà cung cấp cần ghi nợ. Ví dụ: \"ghi nợ nhà cung cấp Minh Phát 500k tiền hàng\"."
            }

        product_name = entities.get("product")
        raw_qty = entities.get("quantity")
        raw_unit_price = first_value(entities.get("price"), entities.get("unit_price"))
        raw_amount = first_value(
            entities.get("original_amount"),
            entities.get("amount"),
            entities.get("total_price"),
        )
        unit = entities.get("unit")

        # Có nói số tiền nhưng = 0 / âm (vd: "ghi nợ NCC X 0 tiền hàng") -> báo rõ, không hỏi lại "chưa nói"
        if is_not_positive(raw_amount) or (raw_amount is None and is_not_positive(raw_unit_price)):
            return {
                "success": False,
                "status": "invalid_amount",
                "intent": intent,
                "missing_fields": ["price"],
                "message": (
                    f"Số tiền ghi nợ phải lớn hơn 0. Vui lòng nói lại số tiền nợ nhà cung cấp {supplier_name}. "
                    f"Ví dụ: \"ghi nợ nhà cung cấp {supplier_name} 500k tiền hàng\"."
                )
            }

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
                "message": (
                    f"Bạn chưa nói số tiền nợ nhà cung cấp {supplier_name}. "
                    f"Ví dụ: \"ghi nợ nhà cung cấp {supplier_name} 500k tiền hàng\"."
                )
            }

        supplier_id = entities.get("supplier_id")
        is_new_supplier = False
        if not supplier_id:
            db = get_db_session()
            try:
                try:
                    db_supplier = InventoryLookupRepository(db).get_supplier_by_name_strict(user_id, str(supplier_name))
                except AmbiguousMatchError as amb:
                    return {
                        "success": False,
                        "status": "need_information",
                        "intent": intent,
                        "missing_fields": ["supplier"],
                        "candidates": amb.candidates,
                        "message": str(amb)
                    }
                if db_supplier:
                    supplier_id = db_supplier.supplier_id
                    if db_supplier.supplier_name:
                        supplier_name = db_supplier.supplier_name
                else:
                    # Chưa có nhà cung cấp: hỏi tạo mới, tạo thật khi người dùng xác nhận
                    is_new_supplier = True
            finally:
                db.close()

        payload = build_payload(entities=entities, text=text)
        payload["supplier_id"] = supplier_id
        payload["supplier_name"] = supplier_name
        if is_new_supplier:
            payload[NEW_SUPPLIER_KEY] = True
        payload["original_amount"] = original_amount
        payload["amount"] = original_amount
        payload["total_amount"] = original_amount
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
            "new_supplier": is_new_supplier,
            "message": (
                f"{new_supplier_question(supplier_name) if is_new_supplier else ''}"
                f"{'Nếu đồng ý, hệ thống sẽ tạo nhà cung cấp và ghi nợ cho ' if is_new_supplier else 'Bạn có chắc muốn ghi nợ cho nhà cung cấp '}"
                f"{supplier_name} "
                f"số tiền {original_amount:,.0f}đ{detail_str}{'.' if is_new_supplier else ' không?'}"
            )
        }
