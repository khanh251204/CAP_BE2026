"""
OCR hóa đơn nhập hàng: ảnh -> văn bản -> items[] -> đối chiếu danh mục -> bản nháp chờ xác nhận.

Cùng khuôn hai pha của giọng nói: dựng nháp, lưu SessionStoreService (waiting_confirmation),
người dùng xác nhận qua POST /agent/pending-action/confirmation (intent mua_hang, payload.items).
Bản nháp chưa tin cậy (dòng lệch, hàng chưa có trong danh mục) trả need_review: vẫn lưu phiên chờ nhưng
app bắt buộc gửi lại items đã sửa, và backend kiểm lại từng dòng trước khi ghi.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai.ocr import preprocess
from app.ai.ocr.diacritics import restore_diacritics
from app.ai.ocr import engine
from app.ai.ocr.receipt_parser import parse_receipt
from app.ai.ocr.text_utils import extract_total
from app.repositories.inventory.inventory_lookup_repo import AmbiguousMatchError, InventoryLookupRepository
from app.services.session_store_service import SessionStoreService

logger = logging.getLogger(__name__)

INTENT = "mua_hang"


def _match_products(db: Session, user_id: int, items: List[Dict[str, Any]]) -> None:
    """Gắn product_id cho từng dòng theo danh mục CỦA user. Gắn match = matched | not_found | ambiguous."""
    repo = InventoryLookupRepository(db)
    for it in items:
        try:
            pid = repo.get_product_id_by_name(user_id=user_id, name=it["name"])
        except AmbiguousMatchError:
            it["match"], it["product_id"] = "ambiguous", None
            continue
        it["product_id"] = pid
        it["match"] = "matched" if pid else "not_found"


def _draft_payload(parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
    items = [{
        "product_id": i["product_id"],
        "product_name": i["name"],
        "quantity": i["quantity"],
        "unit": i["unit"],
        "unit_price": i["unit_price"],
    } for i in parsed["items"]]
    return {
        "items": items,
        "total_amount": parsed["computed_total"],
        # Tên cửa hàng in trên phiếu chỉ để gợi ý: import_goods từ chối supplier_name chưa có trong danh bạ,
        # nên app chọn nhà cung cấp (supplier_id) rồi gửi kèm bản sửa
        "merchant": parsed.get("merchant"),
        "date": parsed.get("date"),
        "input_text": text,
        "source": "OCR",
    }


def check_image(image_bytes: bytes, allow_low_quality: bool = False) -> Tuple[Any, Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Bước nhanh (< 1 giây), chạy ngay trong request: đọc ảnh + cổng chất lượng.
    Trả (ảnh đã xử lý, chất lượng, kết quả trả ngay nếu ảnh bị chặn).
    """
    image, quality = preprocess.prepare(image_bytes, crop=False)
    if not quality["ok"] and not allow_low_quality:
        return image, quality, {"success": False, "status": "poor_quality", "quality": quality,
                                "message": " ".join(quality["messages"])}
    return image, quality, None


def process_image(user_id: int, image: Any, quality: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Bước nặng (OCR + LLM + đối chiếu danh mục), chạy ở luồng nền."""
    ocr = engine.extract_text(image)
    from app.configs.settings import settings
    fixed = restore_diacritics(ocr["text"], enabled=settings.OCR_RESTORE_DIACRITICS)
    text = fixed["text"]
    if not text.strip():
        return {"success": False, "status": "ocr_empty", "quality": quality,
                "message": "Không đọc được chữ nào trên ảnh, bạn chụp lại rõ hơn nhé."}

    parsed = parse_receipt(text, extract_total(text))
    _match_products(db, user_id, parsed["items"])

    result: Dict[str, Any] = {
        "intent": INTENT,
        "quality": quality,
        "ocr": {"text": text, "text_original": ocr["text"], "n_tiles": ocr["n_tiles"], "engine": ocr.get("engine"),
                "latency_ms": ocr["latency_ms"], "diacritics_restored": fixed["changed"]},
        "receipt": parsed,
    }

    items = parsed["items"]
    reliable = (
        parsed["parsed"] and items
        and not parsed["warnings"]
        and all(i["match"] == "matched" for i in items)
    )
    reasons = list(parsed["warnings"])
    if any(i["match"] != "matched" for i in items):
        reasons.append("unmatched_products")
    if not items:
        reasons.append("no_items")

    # Có dòng đọc được thì luôn lưu phiên chờ xác nhận để app sửa rồi gửi lại qua
    # POST /agent/pending-action/confirmation (corrected_transaction.items). Bản sửa luôn được kiểm lại
    # từng dòng ở AgentConfirmService, nên không ghi sổ được khi còn dòng thiếu / sai.
    if items:
        payload = _draft_payload(parsed, text)
        SessionStoreService.save_confirmation(
            session_key=user_id,
            data={"intent": INTENT, "payload": payload, "input_method": "MANUAL"},
            user_id=user_id)
        result["payload"] = payload
    if not reliable:
        return {"success": True, "status": "need_review", "review_reasons": reasons,
                "message": "Mình đọc được hóa đơn nhưng cần bạn kiểm tra lại một số dòng trước khi ghi.", **result}
    return {"success": True, "status": "waiting_confirmation", "message": "Vui lòng xác nhận phiếu nhập hàng",
            **result}


def scan_receipt(user_id: int, image_bytes: bytes, db: Session, allow_low_quality: bool = False) -> Dict[str, Any]:
    """Chạy trọn hai bước một lần (dùng trong test / script)."""
    image, quality, early = check_image(image_bytes, allow_low_quality)
    return early or process_image(user_id, image, quality, db)
