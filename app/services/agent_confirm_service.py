import copy
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.agent_schema import AgentConfirmRequest, CorrectedTransactionSchema
from app.services.data_lake_service import DataLakeService
from app.models.voice_record_model import VoiceRecord
from app.models.transaction_model import Transaction

logger = logging.getLogger(__name__)

# Lệnh chỉ thao tác kho (không phát sinh tiền)
STOCK_INTENTS = ("nhap_kho", "xuat_kho", "hang_hong", "kiem_kho")


class AgentConfirmService:
    @staticmethod
    def validate_and_prepare_payload(
        pending_payload: Dict[str, Any],
        intent: str,
        corrected: CorrectedTransactionSchema,
        user_id: int
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """
        Xử lý bản sửa đổi của người dùng:
        1. Validate theo intent validator hiện có (ban_hang, mua_hang...)
        2. Tính toán lại subtotal và total_amount ở Backend (không tin client)
        3. Tính diff và xác định correction_type
        """
        payload = copy.deepcopy(pending_payload)
        corr_dict = corrected.model_dump(exclude_unset=True)

        # 1. Chạy validator theo intent
        if intent == "ban_hang":
            from app.ai.intents.ban_hang.validator import validate as validate_ban_hang
            # Lấy đúng giá trị người dùng vừa sửa nếu có truyền
            prod_val = corr_dict["product_name"] if "product_name" in corr_dict else (corr_dict.get("product") if "product" in corr_dict else payload.get("product_name"))
            qty_val = corr_dict["quantity"] if "quantity" in corr_dict else payload.get("quantity")
            unit_val = corr_dict["unit"] if "unit" in corr_dict else payload.get("unit")
            val_entities = {
                "product": prod_val,
                "quantity": qty_val,
                "unit": unit_val
            }
            # Nếu có danh sách items
            if corr_dict.get("items"):
                for idx, it in enumerate(corr_dict["items"]):
                    it_dict = it if isinstance(it, dict) else it.model_dump(exclude_unset=True)
                    it_qty = it_dict.get("quantity")
                    if it_qty is None or float(it_qty) <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Sản phẩm thứ {idx + 1} có số lượng không hợp lệ (phải > 0)"
                        )
                    it_ent = {
                        "product": it_dict.get("product_name") or it_dict.get("product"),
                        "quantity": it_qty,
                        "unit": it_dict.get("unit")
                    }
                    val_res = validate_ban_hang(it_ent)
                    if not val_res.get("success"):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Sản phẩm thứ {idx + 1} thiếu thông tin bắt buộc: {', '.join(val_res.get('missing_fields', []))}"
                        )
            else:
                if qty_val is not None:
                    try:
                        if float(qty_val) <= 0:
                            raise HTTPException(
                                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="Số lượng sản phẩm phải lớn hơn 0"
                            )
                    except (ValueError, TypeError):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Số lượng sản phẩm không hợp lệ"
                        )
                val_res = validate_ban_hang(val_entities)
                if not val_res.get("success"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Dữ liệu bán hàng thiếu thông tin: {', '.join(val_res.get('missing_fields', []))}"
                    )

        elif intent in ("mua_hang", "nhap_hang"):
            from app.ai.intents.mua_hang.validator import validate as validate_mua_hang
            prod_val = corr_dict["product_name"] if "product_name" in corr_dict else (corr_dict.get("product") if "product" in corr_dict else payload.get("product_name"))
            qty_val = corr_dict["quantity"] if "quantity" in corr_dict else payload.get("quantity")
            unit_val = corr_dict["unit"] if "unit" in corr_dict else payload.get("unit")
            # Validator mua_hang bắt buộc `price` → lấy giá user sửa, nếu không thì giá trong draft
            if corr_dict.get("unit_price") is not None:
                price_in = corr_dict["unit_price"]
            elif corr_dict.get("price") is not None:
                price_in = corr_dict["price"]
            elif payload.get("unit_price") is not None:
                price_in = payload["unit_price"]
            else:
                price_in = payload.get("price")
            val_entities = {
                "product": prod_val,
                "quantity": qty_val,
                "unit": unit_val,
                "price": price_in,
            }
            if corr_dict.get("items"):
                # Phiếu nhiều dòng (vd: từ OCR hóa đơn): kiểm từng dòng, không dùng trường đơn sản phẩm
                for idx, it in enumerate(corr_dict["items"]):
                    it_dict = it if isinstance(it, dict) else it.model_dump(exclude_unset=True)
                    it_price = it_dict.get("unit_price") if it_dict.get("unit_price") is not None else it_dict.get("price")
                    try:
                        bad_qty = float(it_dict.get("quantity")) <= 0
                    except (ValueError, TypeError):
                        bad_qty = True
                    try:
                        bad_price = it_price is None or float(it_price) <= 0
                    except (ValueError, TypeError):
                        bad_price = True
                    has_product = it_dict.get("product_id") or it_dict.get("product_name") or it_dict.get("product")
                    if bad_qty or bad_price or not has_product:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Dòng {idx + 1} thiếu hoặc sai tên hàng / số lượng / giá nhập (phải > 0)"
                        )
            elif qty_val is not None:
                try:
                    if float(qty_val) <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Số lượng sản phẩm phải lớn hơn 0"
                        )
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Số lượng sản phẩm không hợp lệ"
                    )
            val_res = {"success": True} if corr_dict.get("items") else validate_mua_hang(val_entities)
            if not val_res.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Dữ liệu nhập hàng thiếu thông tin: {', '.join(val_res.get('missing_fields', []))}"
                )


        # 2. Cập nhật và tính toán lại subtotal, total_amount ở Backend
        if corr_dict.get("items"):
            calc_total = 0.0
            recalculated_items = []
            for it in corr_dict["items"]:
                it_dict = it if isinstance(it, dict) else it.model_dump(exclude_unset=True)
                qty = float(it_dict.get("quantity") or 0)
                price = float(it_dict.get("unit_price") if it_dict.get("unit_price") is not None else (it_dict.get("price") or 0))
                # Backend tính lại subtotal - BỎ QUA subtotal client gửi
                subtotal = qty * price
                calc_total += subtotal
                recalculated_items.append({
                    "product_id": it_dict.get("product_id"),
                    "product_name": it_dict.get("product_name") or it_dict.get("product"),
                    "quantity": qty,
                    "unit": it_dict.get("unit") or "",
                    "unit_price": price,
                    "subtotal": subtotal
                })
            payload["items"] = recalculated_items
            payload["total_amount"] = calc_total
        else:
            # Giao dịch đơn sản phẩm
            qty = float(corr_dict.get("quantity") if corr_dict.get("quantity") is not None else payload.get("quantity", 0))
            price_val = corr_dict.get("unit_price") if corr_dict.get("unit_price") is not None else corr_dict.get("price")
            if price_val is None:
                price_val = payload.get("unit_price") if payload.get("unit_price") is not None else payload.get("price", 0)
            price = float(price_val or 0)
            # Backend tính lại subtotal
            subtotal = qty * price
            payload["product_name"] = corr_dict.get("product_name") or corr_dict.get("product") or payload.get("product_name")
            if corr_dict.get("product_id"):
                payload["product_id"] = corr_dict["product_id"]
            payload["quantity"] = qty
            payload["unit"] = corr_dict.get("unit") or payload.get("unit")
            payload["unit_price"] = price
            payload["subtotal"] = subtotal
            payload["total_amount"] = subtotal

        # Cập nhật thông tin đối tác & thanh toán
        if "customer_name" in corr_dict or "customer" in corr_dict:
            payload["customer_name"] = corr_dict.get("customer_name") or corr_dict.get("customer")
        if "customer_id" in corr_dict:
            payload["customer_id"] = corr_dict["customer_id"]
        if "supplier_name" in corr_dict or "supplier" in corr_dict:
            payload["supplier_name"] = corr_dict.get("supplier_name") or corr_dict.get("supplier")
        if "supplier_id" in corr_dict:
            payload["supplier_id"] = corr_dict["supplier_id"]
        if "payment_status" in corr_dict or "payment" in corr_dict:
            payload["payment_status"] = corr_dict.get("payment_status") or corr_dict.get("payment")
        if "amount_paid" in corr_dict and corr_dict["amount_paid"] is not None:
            payload["amount_paid"] = float(corr_dict["amount_paid"])
        if "amount" in corr_dict and corr_dict["amount"] is not None:
            payload["amount"] = float(corr_dict["amount"])
            payload["total_amount"] = float(corr_dict["amount"])
        if "note" in corr_dict:
            payload["note"] = corr_dict["note"]
        if corr_dict.get("date"):
            payload["date"] = corr_dict["date"]
        if corr_dict.get("category_id"):
            payload["category_id"] = corr_dict["category_id"]
        elif corr_dict.get("category_name") and corr_dict["category_name"] != pending_payload.get("category_name"):
            # Đổi khoản chi bằng tên (không kèm id) -> bỏ id cũ để backend tìm theo tên mới
            payload.pop("category_id", None)
        if corr_dict.get("category_name"):
            # Ghi chú mặc định của chi phí = tên khoản chi cũ -> đổi khoản chi thì đổi theo
            old_category = pending_payload.get("category_name") or pending_payload.get("category")
            if "note" not in corr_dict and payload.get("note") in (None, "", old_category, "Chi phí"):
                payload["note"] = corr_dict["category_name"]
            payload["category_name"] = corr_dict["category_name"]
            payload["category"] = corr_dict["category_name"]

        # Chi phí: số tiền là TỔNG người dùng nhập (không phải SL × đơn giá).
        # MCP create_expense đọc `amount` → phải cập nhật, nếu không bản sửa bị bỏ qua.
        if intent in ("chi_phi", "chi_tien"):
            amt = corr_dict.get("amount") if corr_dict.get("amount") is not None else corr_dict.get("total_amount")
            if amt is not None:
                try:
                    amt = float(amt)
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Số tiền chi phí không hợp lệ"
                    )
                if amt <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Số tiền chi phí phải lớn hơn 0"
                    )
                payload["amount"] = amt
                payload["total_amount"] = amt

        # Ghi nợ: route đọc `amount` / `original_amount`, không đọc total_amount.
        # Nếu user sửa SL / đơn giá mà không sửa số tiền → tính lại số tiền nợ.
        if intent in ("ghi_no_khach_hang", "khach_ghi_no", "ghi_no_nha_cung_cap", "ncc_ghi_no"):
            if corr_dict.get("amount") is None and (
                corr_dict.get("quantity") is not None or corr_dict.get("unit_price") is not None
            ):
                if payload.get("quantity") and payload.get("unit_price") and payload["unit_price"] > 0:
                    payload["amount"] = float(payload["quantity"]) * float(payload["unit_price"])
            if payload.get("amount") is not None:
                payload["original_amount"] = payload["amount"]
                payload["total_amount"] = payload["amount"]

        # Thêm sản phẩm: ProductService ưu tiên `name`/`default_unit` cũ → đồng bộ bản sửa.
        if intent == "them_san_pham":
            if corr_dict.get("product_name"):
                payload["name"] = corr_dict["product_name"]
            if corr_dict.get("unit"):
                payload["default_unit"] = corr_dict["unit"]
            if corr_dict.get("unit_price") is not None:
                payload["price"] = corr_dict["unit_price"]

        # Sửa sản phẩm: route chỉ đọc payload["data"] → đưa bản sửa vào đó.
        if intent == "sua_san_pham":
            data = dict(payload.get("data") or {})
            if corr_dict.get("unit_price") is not None:
                data["unit_price"] = corr_dict["unit_price"]
            if corr_dict.get("unit"):
                data["default_unit"] = corr_dict["unit"]
            new_name = corr_dict.get("product_name")
            if new_name and new_name.strip().lower() != str(pending_payload.get("product_name") or "").strip().lower():
                data["product_name"] = new_name
            # Giữ tên gốc để hiển thị / diff, không ghi đè bằng tên mới
            payload["product_name"] = pending_payload.get("product_name")
            payload["data"] = data

        # Lệnh kho (nhập / xuất / hỏng / kiểm kê): service tìm sản phẩm theo product_id trước.
        # Người dùng đổi sang tên khác mà app không gửi id mới -> bỏ id cũ để tìm theo tên mới,
        # nếu không bản sửa bị bỏ qua và thao tác ghi vào sản phẩm cũ.
        if intent in STOCK_INTENTS:
            new_name = corr_dict.get("product_name") or corr_dict.get("product")
            old_name = pending_payload.get("product_name")
            if (
                new_name
                and not corr_dict.get("product_id")
                and str(new_name).strip().lower() != str(old_name or "").strip().lower()
            ):
                payload.pop("product_id", None)
                # Đơn vị cũ thuộc sản phẩm cũ: để service lấy đơn vị của sản phẩm mới
                if "unit" not in corr_dict:
                    payload["unit"] = None
            min_qty_ok = (lambda q: q >= 0) if intent == "kiem_kho" else (lambda q: q > 0)
            if not min_qty_ok(float(payload.get("quantity") or 0)):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Số lượng kiểm kê không được âm" if intent == "kiem_kho" else "Số lượng phải lớn hơn 0"
                )

        # 3. Tính diff và correction_type
        diff_ai: Dict[str, Any] = {}
        diff_corr: Dict[str, Any] = {}

        fields_to_check = [
            ("product_name", "product_name", "product"),
            ("quantity", "quantity", "quantity"),
            ("unit_price", "unit_price", "price"),
            ("unit", "unit", "unit"),
            ("customer_name", "customer_name", "customer"),
            ("supplier_name", "supplier_name", "supplier"),
            ("payment_status", "payment_status", "payment"),
            ("amount_paid", "amount_paid", "amount_paid"),
            ("amount", "amount", "amount"),
        ]

        for p_key, c_key, label in fields_to_check:
            orig_val = pending_payload.get(p_key)
            new_val = payload.get(c_key)
            if orig_val is not None and new_val is not None:
                if isinstance(orig_val, (int, float)) and isinstance(new_val, (int, float)):
                    if abs(float(orig_val) - float(new_val)) > 1e-4:
                        diff_ai[label] = orig_val
                        diff_corr[label] = new_val
                elif str(orig_val).strip().lower() != str(new_val).strip().lower():
                    diff_ai[label] = orig_val
                    diff_corr[label] = new_val

        diff = {
            "ai": diff_ai,
            "correction": diff_corr
        }

        # Xác định correction_type
        changed_keys = list(diff_ai.keys())
        if len(changed_keys) == 1:
            if "price" in changed_keys:
                correction_type = "PRICE_CORRECTION"
            elif "quantity" in changed_keys:
                correction_type = "QUANTITY_CORRECTION"
            elif "product" in changed_keys:
                correction_type = "PRODUCT_CORRECTION"
            else:
                correction_type = "FIELD_CORRECTION"
        elif len(changed_keys) > 1:
            correction_type = "MULTI_FIELD_CORRECTION"
        else:
            correction_type = "CONFIRM_WITHOUT_CHANGE"

        return payload, diff, correction_type
