# app/routes/ocr_route.py
import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.ocr import preprocess
from app.ai.ocr.engine import OcrUnavailableError
from app.ai.ocr.service import scan_receipt
from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_permission
from app.configs.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post(
    "/ocr/receipts",
    tags=["OCR"],
    dependencies=[Depends(require_permission("voice:use")), Depends(require_permission("transaction:purchase"))],
)
async def scan_receipt_image(
    image: UploadFile = File(..., description="Ảnh hóa đơn nhập hàng (jpg/png/webp)"),
    allow_low_quality: bool = Form(False, description="Vẫn OCR dù ảnh không qua cổng chất lượng"),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Ảnh hóa đơn -> bản nháp phiếu nhập hàng (intent mua_hang, nhiều dòng).
    status: waiting_confirmation (xác nhận qua /agent/pending-action/confirmation) | need_review |
    poor_quality | ocr_empty.
    """
    if not settings.OCR_ENABLED:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Tính năng quét hóa đơn đang tắt")
    if (image.content_type or "").lower() not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Chỉ hỗ trợ ảnh jpg, png, webp")

    limit = settings.OCR_MAX_IMAGE_MB * 1024 * 1024
    data = await image.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Ảnh vượt quá {settings.OCR_MAX_IMAGE_MB} MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ảnh rỗng")

    try:
        return await asyncio.to_thread(scan_receipt, current_user_id, data, db, allow_low_quality)
    except preprocess.InvalidImageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except OcrUnavailableError as e:
        logger.error("[OCR] Không khả dụng: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dịch vụ quét hóa đơn chưa sẵn sàng")
    except Exception:
        logger.error("[OCR] Lỗi xử lý ảnh", exc_info=True)
        return {"success": False, "message": "Lỗi xử lý hóa đơn"}
