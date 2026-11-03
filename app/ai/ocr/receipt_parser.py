"""
Văn bản OCR của hóa đơn -> danh sách dòng hàng (items[]).

LLM chỉ TRÍCH XUẤT (tên, số lượng, đơn giá, thành tiền, tổng). Mọi phép tính và đối chiếu do backend làm:
số lượng x đơn giá = thành tiền, tổng các dòng = tổng phiếu. Dòng lệch được gắn cảnh báo để người dùng sửa
ở màn hình xác nhận, không bao giờ tự sửa im lặng.
"""
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PARSE_MODEL = "openai/gpt-oss-120b"
TOLERANCE = Decimal("1")  # lệch tối đa 1đ do làm tròn

SYSTEM_PROMPT = (
    "Bạn trích xuất dữ liệu từ văn bản OCR của hóa đơn / phiếu mua hàng tiếng Việt. "
    "Chỉ trả về JSON đúng dạng:\n"
    '{"merchant": string|null, "date": "YYYY-MM-DD"|null, "total": number|null, '
    '"items": [{"name": string, "quantity": number|null, "unit": string|null, '
    '"unit_price": number|null, "amount": number|null}]}\n'
    "Quy tắc: mỗi mặt hàng một phần tử; số tiền là số nguyên VND, bỏ dấu chấm/phẩy ngăn cách nghìn; "
    "không đưa dòng tổng cộng, thuế, tiền khách đưa, tiền thừa, chiết khấu vào items; "
    "trường nào không đọc được thì để null, TUYỆT ĐỐI không đoán hay tự tính; giữ nguyên tên hàng như trên phiếu."
)


def _dec(v: Any) -> Optional[Decimal]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, str):
        v = re.sub(r"[^\d.,-]", "", v)
        if re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", v):   # 1.250.000 -> nghìn
            v = re.sub(r"[.,]", "", v)
        v = v.replace(",", ".")
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _num(d: Optional[Decimal]) -> Optional[float]:
    if d is None:
        return None
    return int(d) if d == d.to_integral_value() else float(d)


def _extract_json(raw: str) -> Dict:
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
    raw = re.sub(r"^```\w*\n|\n```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise
        data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM không trả về JSON object")
    return data


def _call_llm(text: str) -> Dict:
    from app.ai.llm.groq_client_pool import get_groq_pool
    resp = get_groq_pool().call(lambda c: c.chat.completions.create(
        model=PARSE_MODEL, temperature=0.0, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
    ))
    return _extract_json(resp.choices[0].message.content or "")


def validate_items(raw_items: List[Any], receipt_total: Optional[int]) -> Dict:
    """
    Làm sạch và đối chiếu các dòng hàng. Trả {"items", "computed_total", "total_matches", "warnings"}.
    Cảnh báo theo dòng: missing_quantity, missing_price, amount_mismatch (kèm expected_amount).
    """
    items, warnings = [], []
    for idx, it in enumerate(raw_items or []):
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        qty, price, amount = _dec(it.get("quantity")), _dec(it.get("unit_price")), _dec(it.get("amount"))
        if qty is not None and qty <= 0:
            qty = None
        if price is not None and price <= 0:
            price = None
        if amount is not None and amount <= 0:
            amount = None
        line_warn: List[str] = []
        entry: Dict[str, Any] = {"line": idx + 1}

        if qty is not None and price is not None:
            expected = qty * price
            if amount is None:
                amount = expected
            elif abs(expected - amount) > TOLERANCE:
                line_warn.append("amount_mismatch")
                entry["expected_amount"] = _num(expected)
        elif qty is not None and amount is not None:
            price = amount / qty
        elif price is not None and amount is not None:
            qty = amount / price
        else:
            if qty is None:
                line_warn.append("missing_quantity")
            if price is None:
                line_warn.append("missing_price")

        entry.update({
            "name": name,
            "quantity": _num(qty),
            "unit": (str(it.get("unit")).strip() or None) if it.get("unit") else None,
            "unit_price": _num(price),
            "amount": _num(amount),
            "warnings": line_warn,
        })
        items.append(entry)

    computed = sum((Decimal(str(i["amount"])) for i in items if i["amount"] is not None), Decimal(0))
    total_matches = None
    if receipt_total is not None and items:
        total_matches = abs(computed - Decimal(receipt_total)) <= TOLERANCE
        if not total_matches:
            warnings.append("total_mismatch")
    if any(i["warnings"] for i in items):
        warnings.append("line_issues")
    return {"items": items, "computed_total": _num(computed) if items else None,
            "total_matches": total_matches, "warnings": warnings}


def parse_receipt(text: str, ocr_total: Optional[int]) -> Dict:
    """
    Trả {"merchant", "date", "total", "items", "computed_total", "total_matches", "warnings", "parsed"}.
    Tổng tiền ưu tiên số regex đọc trực tiếp từ chữ OCR, LLM chỉ là phương án dự phòng.
    LLM lỗi -> parsed=False, items rỗng; người dùng nhập tay, không bịa dữ liệu.
    """
    try:
        data = _call_llm(text)
    except Exception as e:  # noqa: BLE001
        logger.warning("[OCR] Trích xuất items thất bại: %s", e)
        return {"merchant": None, "date": None, "total": ocr_total, "items": [], "computed_total": None,
                "total_matches": None, "warnings": ["parse_failed"], "parsed": False}
    llm_total = _dec(data.get("total"))
    total = ocr_total if ocr_total is not None else (int(llm_total) if llm_total is not None else None)
    checked = validate_items(data.get("items") or [], total)
    date = data.get("date") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("date") or "")) else None
    return {"merchant": (str(data["merchant"]).strip() or None) if data.get("merchant") else None,
            "date": date, "total": total, "parsed": True, **checked}
