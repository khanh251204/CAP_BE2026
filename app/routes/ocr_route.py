# app/routes/ocr_route.py
import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.ai.ocr import jobs, preprocess
from app.ai.ocr.engine import OcrUnavailableError
from app.ai.ocr.service import check_image, process_image
from app.configs.database import SessionLocal
from app.configs.jwt import get_current_user_id, require_permission
from app.configs.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
OCR_PERMISSIONS = [Depends(require_permission("voice:use")), Depends(require_permission("transaction:purchase"))]


def _run_job(user_id: int, image, quality) -> dict:
    # Luồng nền không dùng session của request (đã đóng khi request trả về)
    with SessionLocal() as db:
        return process_image(user_id, image, quality, db)


@router.post("/ocr/receipts", tags=["OCR"], dependencies=OCR_PERMISSIONS)
async def scan_receipt_image(
    image: UploadFile = File(..., description="Ảnh hóa đơn nhập hàng (jpg/png/webp)"),
    allow_low_quality: bool = Form(False, description="Vẫn OCR dù ảnh không qua cổng chất lượng"),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Ảnh hóa đơn -> bản nháp phiếu nhập hàng (intent mua_hang, nhiều dòng), chạy nền.
    - Ảnh không qua cổng chất lượng: trả ngay status=poor_quality.
    - Còn lại: 202 {status: processing, job_id}; hỏi kết quả ở GET /ocr/receipts/jobs/{job_id}.
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
        img, quality, early = await asyncio.to_thread(check_image, data, allow_low_quality)
    except preprocess.InvalidImageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    if early:
        return early

    job_id = jobs.submit(current_user_id, lambda: _run_job(current_user_id, img, quality))
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"success": True, "status": "processing", "job_id": job_id,
                 "message": "Đang đọc hóa đơn, vui lòng chờ trong giây lát."},
    )


@router.get("/ocr/receipts/jobs/{job_id}", tags=["OCR"], dependencies=OCR_PERMISSIONS)
async def get_scan_result(job_id: str, current_user_id: int = Depends(get_current_user_id)):
    """Kết quả quét: status=processing (hỏi lại sau) | waiting_confirmation | need_review | ocr_empty | failed."""
    job = jobs.get(current_user_id, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy lượt quét này (có thể đã hết hạn)")
    if not job["done"]:
        return {"success": True, "status": "processing", "job_id": job_id}

    error = job["error"]
    if error is None:
        return job["result"]
    if isinstance(error, OcrUnavailableError):
        logger.error("[OCR] Không khả dụng: %s", error)
        message = "Dịch vụ quét hóa đơn chưa sẵn sàng, bạn thử lại sau nhé."
    else:
        logger.error("[OCR] Lỗi xử lý ảnh", exc_info=error)
        message = "Lỗi xử lý hóa đơn, bạn thử lại sau nhé."
    return {"success": False, "status": "failed", "job_id": job_id, "message": message}
