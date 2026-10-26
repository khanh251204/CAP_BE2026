import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_permission, require_admin_area
from app.schemas.admin_voice_schema import (
    AdminVoiceListResponse,
    AdminVoiceDetailResponse,
    AdminVoiceAiResultResponse,
    AdminUserCorrectionListResponse,
    AdminUserCorrectionItem,
    AdminVoicePagination,
)
from app.services.admin_voice_service import AdminVoiceService
from app.services.user_correction_service import UserCorrectionService

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Voice Processing History"],
    dependencies=[Depends(require_admin_area)]
)


@router.get(
    "/voice-records",
    response_model=AdminVoiceListResponse,
    summary="Xem danh sách lịch sử xử lý voice",
    description="Truy vấn danh sách lịch sử xử lý voice có phân trang, tìm kiếm transcript và bộ lọc theo người dùng, intent, status, độ tin cậy, thời gian.",
    dependencies=[Depends(require_permission("admin_voice:read"))],
)
def list_voice_processing(
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi trên một trang"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm trong transcript"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng"),
    intent: Optional[str] = Query(None, description="Lọc theo mã intent"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái xử lý: SUCCESS, FAILED, PROCESSING, REVIEW"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Độ tin cậy tối thiểu"),
    confidence_max: Optional[float] = Query(None, ge=0.0, le=1.0, description="Độ tin cậy tối đa"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Thời điểm bắt đầu (ISO 8601)"),
    to_date: Optional[datetime] = Query(None, alias="to", description="Thời điểm kết thúc (ISO 8601)"),
    db: Session = Depends(get_db)
):
    return AdminVoiceService.list_voice_records(
        db=db,
        page=page,
        limit=limit,
        search=search,
        user_id=user_id,
        intent=intent,
        status_filter=status,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        from_date=from_date,
        to_date=to_date
    )


@router.get(
    "/voice-corrections",
    response_model=AdminUserCorrectionListResponse,
    summary="Danh sách hiệu chỉnh người dùng (Human-in-the-Loop)",
    description="Truy xuất danh sách bản ghi người dùng đã xác nhận hoặc chỉnh sửa kết quả AI, phục vụ đánh giá (Evaluation) và cải tiến mô hình.",
    dependencies=[Depends(require_permission("admin_voice:read"))],
)
def list_user_corrections(
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi trên một trang"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng"),
    correction_type: Optional[str] = Query(None, description="Lọc theo loại hiệu chỉnh"),
    db: Session = Depends(get_db)
):
    items, total = UserCorrectionService.list_corrections(
        db=db,
        page=page,
        limit=limit,
        user_id=user_id,
        correction_type=correction_type
    )
    total_pages = math.ceil(total / limit) if total > 0 else 0
    return AdminUserCorrectionListResponse(
        items=[
            AdminUserCorrectionItem(
                id=c.id,
                user_id=c.user_id,
                voice_record_id=c.voice_record_id,
                transaction_id=c.transaction_id,
                correction_type=c.correction_type,
                original_ai_result=c.original_ai_result or {},
                corrected_result=c.corrected_result or {},
                diff=c.diff or {},
                extra_metadata=c.extra_metadata,
                created_at=c.created_at
            )
            for c in items
        ],
        pagination=AdminVoicePagination(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages
        )
    )


@router.get(
    "/voice-records/{id}",

    response_model=AdminVoiceDetailResponse,
    summary="Xem chi tiết một bản ghi xử lý voice",
    description="Truy xuất đầy đủ thông tin chi tiết của một bản ghi voice processing: thông tin người dùng, file ghi âm, kết quả AI (transcript, intent, entities, confidence), validation, transaction liên kết và processing logs.",
    dependencies=[Depends(require_permission("admin_voice:read"))],
)
def get_voice_processing_detail(
    id: int,
    db: Session = Depends(get_db)
):
    return AdminVoiceService.get_voice_record_detail(db=db, voice_id=id)


@router.get(
    "/voice-records/{id}/ai-result",
    response_model=AdminVoiceAiResultResponse,
    summary="Xem kết quả AI của bản ghi xử lý voice",
    description="Xem kết quả AI đã xử lý từ một Voice Record: transcript, intent, entities, confidence thực tế, validation, user correction, transaction và processing metadata.",
    dependencies=[Depends(require_permission("admin_voice:read"))],
)
def get_voice_ai_result(
    id: int,
    db: Session = Depends(get_db)
):
    return AdminVoiceService.get_voice_ai_result(db=db, voice_id=id)


@router.get(
    "/voice-records/{id}/audio",
    summary="Nghe/tải file âm thanh ghi âm",
    description="Endpoint stream file âm thanh gốc bảo mật dành riêng cho Admin, không làm lộ đường dẫn hệ thống nội bộ.",
    dependencies=[Depends(require_permission("admin_voice:read"))],
)
def stream_voice_audio(
    id: int,
    db: Session = Depends(get_db)
):
    file_path, media_type, filename = AdminVoiceService.get_audio_file_path(db=db, voice_id=id)
    if media_type == "url":
        return RedirectResponse(url=file_path, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )
