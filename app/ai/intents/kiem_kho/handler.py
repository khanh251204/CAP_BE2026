from decimal import Decimal
from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.services.product_unit_service import counted_stock, pack_unit_of, whole_packs
from app.services.sales_policy import ERROR_INVALID_UNIT, is_unit_valid, invalid_unit_message, to_product_unit, unit_ratio
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
        book = float(stock.get("quantity") or 0)

        # Đếm theo gói đã khai báo (1 gói = 300 g): so số gói nguyên, bỏ gói đang dùng dở
        pack = pack_unit_of(stock.get("units"), entities.get("unit"))
        if pack:
            return self._pack_count_draft(intent, entities, text, stock, pack, actual, book)

        # Quy đổi đơn vị cùng loại (kg <-> g, lít <-> ml...); khác loại mới báo lỗi
        converted = to_product_unit(entities, product_unit, stock.get("units"))
        if converted is None:
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
        if converted is not entities:
            ratio = unit_ratio(entities.get("unit"), product_unit, stock.get("units"))
            actual = float(Decimal(str(actual)) * ratio)
            entities = converted

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

    @staticmethod
    def _pack_count_draft(intent, entities, text, stock, pack, counted, book) -> dict:
        """Bản nháp kiểm kho theo gói nguyên: chỉ ghi phần gói lệch, giữ phần lẻ của gói đang dùng."""
        product_name = stock.get("product_name")
        stock_unit = stock.get("default_unit") or ""
        pack_name = pack["unit_name"]
        factor = Decimal(str(pack["factor"]))
        whole, remainder = whole_packs(book, pack)
        actual = float(counted_stock(book, counted, pack_name, stock_unit, stock.get("units")))
        delta = actual - book
        diff_packs = Decimal(str(counted)) - whole

        if diff_packs == 0:
            diff_text = "khớp sổ sách"
        elif diff_packs > 0:
            diff_text = f"dư {float(diff_packs):g} {pack_name} ({float(diff_packs * factor):g} {stock_unit})"
        else:
            diff_text = f"thiếu {float(-diff_packs):g} {pack_name} ({float(-diff_packs * factor):g} {stock_unit})"
        odd = f" + {float(remainder):g} {stock_unit} gói đang dùng" if remainder > 0 else ""

        payload = build_payload(entities={**entities, "unit": stock_unit}, text=text)
        payload.update({
            "product_id": stock.get("product_id"),
            "product_name": product_name,
            "quantity": actual,
            "unit": stock_unit,
            # Xác nhận: service tính lại từ số gói đếm trên tồn mới nhất
            "count_unit": pack_name,
            "counted": float(counted),
            "quantity_before": book,
            "delta": delta,
        })
        return {
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
                f"Sổ sách {product_name} còn {float(whole):g} {pack_name}{odd}, "
                f"thực tế đếm được {float(counted):g} {pack_name} ({diff_text}). "
                + ("Không cần điều chỉnh, bạn có muốn ghi nhận lần kiểm kho này?" if diff_packs == 0
                   else f"Bạn có muốn cập nhật tồn kho thành {float(counted):g} {pack_name}{odd}?")
            ),
        }
