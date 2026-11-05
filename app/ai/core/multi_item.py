"""
Nhiều sản phẩm trong một câu ("Bán 2 lon coca và 3 gói mì cho chị Lan").

LLM chỉ trích xuất: entities.items = [{product, quantity, unit, price, total_price}, ...].
Backend quyết định phần còn lại:
- Mỗi dòng đi qua đúng handler một sản phẩm (ban_hang / mua_hang), nên dùng lại toàn bộ kiểm tra
  tồn kho, đơn vị, giá, định mức nguyên liệu.
- Một dòng lỗi thì huỷ cả bản nháp, báo rõ dòng nào.
- Bản nháp là MỘT giao dịch nhiều dòng (payload["items"]); tổng tiền do backend tính.
  Bước xác nhận (InventoryService.sell_goods / import_goods) đã xử lý payload["items"] trong một
  database transaction, lỗi thì rollback toàn bộ.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.ai.intents.missing_info import clean_entities_for_intent, drop_unspoken_quantity
from app.services.new_customer_service import NEW_CUSTOMER_KEY
from app.services.new_product_service import NEW_PRODUCT_KEY
from app.services.new_supplier_service import NEW_SUPPLIER_KEY
from app.services.sales_policy import is_unpaid_payment, resolve_total_price

MAX_ITEMS = 20

SALE_INTENTS = ("ban_hang",)
PURCHASE_INTENTS = ("mua_hang", "nhap_hang")
MULTI_ITEM_INTENTS = SALE_INTENTS + PURCHASE_INTENTS

# LLM hay gán "bán nợ A, B cho chị Lan" vào intent ghi nợ: có hàng thì đây là bán / nhập hàng chưa thu / trả tiền
_DEBT_TO_GOODS_INTENT = {
    "khach_ghi_no": "ban_hang",
    "ghi_no_khach_hang": "ban_hang",
    "ghi_no_nha_cung_cap": "mua_hang",
    "ncc_ghi_no": "mua_hang",
}

# Trường dùng chung cho cả đơn, chép xuống từng dòng
_SHARED_KEYS = ("customer", "supplier", "payment", "date")
_LINE_KEYS = ("product", "quantity", "unit", "price", "total_price")


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def extract_items(entities: dict) -> list[dict]:
    """Danh sách dòng hợp lệ về mặt hình dạng (có ít nhất tên sản phẩm); [] nếu không phải câu nhiều sản phẩm."""
    raw = (entities or {}).get("items")
    if not isinstance(raw, list):
        return []
    items = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        line = {k: it.get(k) for k in _LINE_KEYS}
        # LLM đôi khi dùng tên khác cho cùng một trường
        if _empty(line["product"]):
            line["product"] = it.get("product_name") or it.get("name")
        if _empty(line["price"]) and not _empty(it.get("unit_price")):
            line["price"] = it.get("unit_price")
        if _empty(line["product"]):
            continue
        items.append(line)
    return items


def resolve_multi_intent(intent: Optional[str], entities: dict) -> Optional[str]:
    """Intent hàng hoá nếu câu có >= 2 dòng sản phẩm, ngược lại None."""
    if len(extract_items(entities)) < 2:
        return None
    if intent in MULTI_ITEM_INTENTS:
        return intent
    return _DEBT_TO_GOODS_INTENT.get(intent)


def _same_unit(a: Any, b: Any) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def merge_duplicate_items(items: list[dict]) -> list[dict]:
    """
    "Bán 2 coca và 3 coca" -> 1 dòng 5 coca. Chỉ gộp khi cùng đơn vị và không có giá khác nhau,
    để kiểm tra tồn kho tính trên tổng số lượng thật.
    """
    merged: list[dict] = []
    for line in items:
        target = None
        for prev in merged:
            if (
                str(prev["product"]).strip().lower() == str(line["product"]).strip().lower()
                and _same_unit(prev.get("unit"), line.get("unit"))
                and (_empty(prev.get("price")) or _empty(line.get("price")) or prev.get("price") == line.get("price"))
                and _empty(prev.get("total_price")) and _empty(line.get("total_price"))
                and not _empty(prev.get("quantity")) and not _empty(line.get("quantity"))
            ):
                target = prev
                break
        if target is None:
            merged.append(dict(line))
            continue
        try:
            target["quantity"] = float(Decimal(str(target["quantity"])) + Decimal(str(line["quantity"])))
        except Exception:
            merged.append(dict(line))
            continue
        if _empty(target.get("price")):
            target["price"] = line.get("price")
    return merged


def _line_entities(intent: str, shared: dict, line: dict, text: str) -> dict:
    ent = {**shared, **{k: v for k, v in line.items() if not _empty(v)}}
    ent = drop_unspoken_quantity(intent, ent, text)
    ent = clean_entities_for_intent(intent, ent, text)
    return resolve_total_price(intent, ent)


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}đ"
    except (TypeError, ValueError):
        return ""


def _line_summary(p: dict) -> str:
    qty = p.get("quantity")
    qty_txt = f"{float(qty):g}" if qty is not None else ""
    head = " ".join(x for x in (qty_txt, p.get("unit") or "", p.get("product_name") or "") if x)
    price = p.get("unit_price")
    return f"{head} ({_money(price)}/{p.get('unit') or 'đơn vị'})" if price else head


async def build_multi_item_draft(
    router: Any,
    intent: str,
    user_id: int,
    entities: dict,
    text: str,
) -> dict:
    """
    Trả kết quả giống một handler: waiting_confirmation + payload nhiều dòng,
    hoặc lỗi của dòng đầu tiên không hợp lệ (kèm line_index, huỷ cả bản nháp).
    """
    is_sale = intent in SALE_INTENTS
    items = merge_duplicate_items(extract_items(entities))
    if len(items) > MAX_ITEMS:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "message": f"Một lần chỉ ghi tối đa {MAX_ITEMS} sản phẩm. Bạn tách thành nhiều câu giúp mình.",
        }

    # amount_paid / tổng tiền là của cả đơn, không áp xuống từng dòng
    shared = {k: entities.get(k) for k in _SHARED_KEYS if not _empty(entities.get(k))}
    amount_paid = entities.get("amount_paid")

    lines: list[dict] = []
    first: Optional[dict] = None
    for idx, line in enumerate(items, start=1):
        ent = _line_entities(intent, shared, line, text)
        result = await router.route(intent=intent, user_id=user_id, entities=ent, text=text)
        label = f"Dòng {idx} ({line.get('product')})"

        if result.get("status") != "waiting_confirmation":
            # Một dòng lỗi: huỷ cả giao dịch, giữ nguyên status/mã lỗi của handler để app xử lý như bình thường
            failed = dict(result)
            failed["success"] = False
            failed["line_index"] = idx
            failed["message"] = f"{label}: {result.get('message') or 'không hợp lệ'}"
            failed.setdefault("intent", intent)
            return failed

        payload = result.get("payload") or {}
        if payload.get(NEW_PRODUCT_KEY):
            # Mỗi sản phẩm mới cần đơn vị / loại riêng: tạo ở câu riêng cho rõ ràng
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "line_index": idx,
                "missing_fields": ["product"],
                "message": (
                    f"{label}: sản phẩm này chưa có trong danh mục. "
                    f"Hãy thêm sản phẩm trước (hoặc nói riêng một câu cho sản phẩm này), rồi ghi lại đơn nhiều sản phẩm."
                ),
            }
        first = first or result
        lines.append({"result": result, "payload": payload})

    # Nguyên liệu theo định mức: các món dùng chung nguyên liệu phải đủ theo TỔNG, không chỉ từng món
    materials: list[dict] = []
    if is_sale:
        shortage = _combined_material_shortage(lines)
        if shortage:
            shortage["intent"] = intent
            return shortage
        materials = _sum_materials(lines)

    out_items = []
    total = Decimal("0")
    for entry in lines:
        p = entry["payload"]
        qty = Decimal(str(p.get("quantity") or 0))
        price = Decimal(str(p.get("unit_price") or 0))
        subtotal = Decimal(str(p["total_amount"])) if p.get("total_amount") is not None else qty * price
        total += subtotal
        out_items.append({
            "product_id": p.get("product_id"),
            "product_name": p.get("product_name"),
            "quantity": float(qty),
            "unit": p.get("unit") or "",
            "unit_price": float(price),
            "subtotal": float(subtotal),
        })

    base = lines[0]["payload"]
    payload: dict = {
        "items": out_items,
        "total_amount": float(total),
        "input_text": text,
        "date": base.get("date"),
    }
    party_keys = ("customer_id", "customer_name") if is_sale else ("supplier_id", "supplier_name")
    for key in party_keys:
        if base.get(key):
            payload[key] = base[key]
    payload["payment_status"] = base.get("payment_status")
    flag = NEW_CUSTOMER_KEY if is_sale else NEW_SUPPLIER_KEY
    new_party = any(e["payload"].get(flag) for e in lines)
    if new_party:
        payload[flag] = True

    paid: Optional[float] = None
    if amount_paid is not None:
        try:
            paid = float(amount_paid)
        except (TypeError, ValueError):
            paid = 0.0
    elif is_unpaid_payment(base.get("payment_status")):
        paid = 0.0
    if paid is not None:
        payload["amount_paid"] = paid

    unpaid = float(total) - paid if paid is not None else 0.0
    has_debt = unpaid > 0
    party_name = payload.get("customer_name") if is_sale else payload.get("supplier_name")
    party_known = bool(payload.get("customer_id") if is_sale else payload.get("supplier_id")) or new_party
    if has_debt and not party_known:
        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["customer" if is_sale else "supplier"],
            "message": (
                "Đơn bán chưa thanh toán đủ / ghi nợ cần có thông tin Khách hàng để ghi nợ."
                if is_sale
                else "Đơn nhập hàng chưa thanh toán đủ / ghi nợ cần có thông tin Nhà cung cấp để ghi nợ."
            ),
        }

    listing = "; ".join(_line_summary({**i}) for i in out_items)
    debt_txt = ""
    if has_debt:
        who = f" cho {'khách' if is_sale else 'NCC'} '{party_name}'" if party_name else ""
        debt_txt = f" (Chưa thanh toán - ghi nợ{who}: {unpaid:,.0f}đ)"
    verb = "bán" if is_sale else "nhập"
    if has_debt and is_sale:
        verb = "bán nợ"
    party_txt = ""
    if party_name:
        party_txt = f" cho khách '{party_name}'" if is_sale else f" từ nhà cung cấp '{party_name}'"
    mat_txt = ""
    if materials:
        mat_txt = " (chế biến theo định mức, dùng " + ", ".join(
            f"{m['quantity']:g} {m.get('unit') or ''} {m['material_name']}".replace("  ", " ") for m in materials
        ) + ")"

    message = (
        f"Bạn có chắc muốn {verb} {len(out_items)} sản phẩm{party_txt}: {listing}. "
        f"Tổng {_money(total)}{debt_txt}{mat_txt}?"
    )

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "export_inventory" if is_sale else "import_inventory",
        "multi_item": True,
        "item_count": len(out_items),
        "new_product": None,
        "payload": payload,
        "new_customer": bool(new_party and is_sale),
        "new_supplier": bool(new_party and not is_sale),
        "materials": materials,
        "bom_missing": any(e["result"].get("bom_missing") for e in lines),
        "message": message,
    }


# ---------------------------------------------------------------------------
# Nguyên liệu theo định mức (chỉ bán hàng)
# ---------------------------------------------------------------------------
def _sum_materials(lines: list[dict]) -> list[dict]:
    totals: dict[int, dict] = {}
    for entry in lines:
        for m in entry["result"].get("materials") or []:
            mid = int(m["material_product_id"])
            cur = totals.setdefault(mid, {
                "material_product_id": mid,
                "material_name": m.get("material_name") or "",
                "unit": m.get("unit"),
                "quantity": 0.0,
                "quantity_in_stock": m.get("quantity_in_stock"),
            })
            cur["quantity"] += float(m.get("quantity") or 0)
    return [totals[k] for k in sorted(totals)]


def _combined_material_shortage(lines: list[dict]) -> Optional[dict]:
    short = []
    for m in _sum_materials(lines):
        stock = m.get("quantity_in_stock")
        if stock is not None and float(stock) < m["quantity"]:
            short.append(m)
    if not short:
        return None
    from app.services.bom_service import ERROR_INSUFFICIENT_MATERIAL

    detail = "; ".join(
        f"'{m['material_name']}' còn {float(m['quantity_in_stock']):g} {m.get('unit') or ''}, cần {m['quantity']:g} {m.get('unit') or ''}".replace("  ", " ").strip()
        for m in short
    )
    return {
        "success": False,
        "status": "insufficient_material",
        "error_code": ERROR_INSUFFICIENT_MATERIAL,
        "shortages": short,
        "message": f"Không đủ nguyên liệu để làm cả đơn theo định mức: {detail}.",
    }
