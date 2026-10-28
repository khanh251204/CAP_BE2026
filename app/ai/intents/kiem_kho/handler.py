from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.services.sales_policy import ERROR_INVALID_UNIT, is_unit_valid, invalid_unit_message
from .validator import validate
from .payload import build_payload, counted_quantity


class KiemKhoHandler:
    """
    Business workflow cho intent: kiem_kho
    - Hỏi tồn ("coca còn không", "kiểm kho tôm") -> gọi MCP check_stock, trả kết quả ngay.
    - Báo số đếm thực tế ("kiểm kho coca còn 15 lon") -> bản nháp kiểm kê, chờ xác nhận;
      khi xác nhận gọi MCP adjust_stock ghi Inventory_Transaction ADJUSTMENT.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "kiem_kho"
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

        stock = normalize_mcp_result(await call_mcp_tool(
            "check_stock",
            {
                "payload": {"product_name": entities.get("product")},
                "user_id": user_id
            }
        ))

        actual = counted_quantity(entities, text)
        if actual is None or not stock.get("success"):
            # Chỉ hỏi tồn (hoặc không tìm thấy sản phẩm)
            if isinstance(stock, dict):
                stock.setdefault("intent", intent)
            return stock

        if actual < 0:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": ["quantity"],
                "message": "Số lượng kiểm kê không được âm."
            }

        product_name = stock.get("product_name")
        product_unit = stock.get("default_unit") or ""
        if not is_unit_valid(entities.get("unit"), product_unit):
            return {
                "success": False,
                "status": "invalid_unit",
                "error_code": ERROR_INVALID_UNIT,
                "intent": intent,
                "product_name": product_name,
                "unit_requested": entities.get("unit"),
                "default_unit": product_unit,
                "message": invalid_unit_message(product_name, entities.get("unit"), product_unit),
            }

        book = float(stock.get("quantity") or 0)
        delta = actual - book
        unit = product_unit or entities.get("unit") or ""

        payload = build_payload(entities=entities, text=text)
        payload.update({
            "product_id": stock.get("product_id"),
            "product_name": product_name,
            "quantity": actual,
            "unit": unit,
            # Chỉ để hiển thị; khi xác nhận service đọc lại tồn sổ sách mới nhất
            "quantity_before": book,
            "delta": delta,
        })

        if delta == 0:
            diff_text = "khớp sổ sách"
        elif delta > 0:
            diff_text = f"dư {delta:g} {unit}"
        else:
            diff_text = f"thiếu {-delta:g} {unit}"

        return {
            # Kèm thông tin tồn sổ sách như khi hỏi tồn: app bản cũ coi kiem_kho là tra cứu
            # (hiện thẻ tồn kho) vẫn hiển thị đúng thay vì tồn = 0
            **{k: stock.get(k) for k in (
                "product_id", "product_name", "quantity", "min_quantity",
                "stock_status", "unit_price", "default_unit",
            )},
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "action": "adjust_stock",
            "counted_quantity": actual,
            "delta": delta,
            "payload": payload,
            "message": (
                f"Sổ sách {product_name} còn {book:g} {unit}, thực tế đếm được {actual:g} {unit} "
                f"({diff_text}). Bạn có muốn cập nhật tồn kho thành {actual:g} {unit}?"
            )
        }
