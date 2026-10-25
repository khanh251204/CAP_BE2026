from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_permission, require_admin_area
from app.schemas.admin_dataset_schema import (
    AdminDatasetListResponse,
    AdminDatasetDetailResponse,
    AdminDatasetSummaryResponse,
    AdminDatasetIngestResponse,
)
from app.services.admin_dataset_service import AdminDatasetService


class DatasetIngestRequest(BaseModel):
    voice_id: int = Field(..., ge=1, description="ID bản ghi giọng nói (Voice_Record) cần đưa vào dataset")

router = APIRouter(
    prefix="/admin/datasets",
    tags=["Admin - Data Lake & Dataset Management"],
    dependencies=[Depends(require_admin_area)],
)


@router.get(
    "",
    response_model=AdminDatasetListResponse,
    summary="Xem danh sách bộ dữ liệu Data Lake",
    description="Truy vấn danh sách các mẫu dữ liệu trong Data Lake (phân loại RAW, PROCESSED, FEEDBACK, DATASET) có phân trang và bộ lọc.",
    dependencies=[Depends(require_permission("admin_dataset:read"))],
)
def list_dataset(
    page: int = Query(1, ge=1, description="Trang hiện tại (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi trên trang"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm trong transcript"),
    data_type: Optional[str] = Query(None, description="Phân loại: RAW, PROCESSED, FEEDBACK, DATASET"),
    source_type: Optional[str] = Query(None, description="Nguồn: VOICE_PIPELINE"),
    intent: Optional[str] = Query(None, description="Lọc theo intent"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: SUCCESS, FAILED..."),
    from_date: Optional[datetime] = Query(None, alias="from", description="Thời gian bắt đầu"),
    to_date: Optional[datetime] = Query(None, alias="to", description="Thời gian kết thúc"),
    db: Session = Depends(get_db),
):
    return AdminDatasetService.list_dataset(
        db=db,
        page=page,
        limit=limit,
        search=search,
        data_type=data_type,
        source_type=source_type,
        intent=intent,
        status_filter=status,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/summary",
    response_model=AdminDatasetSummaryResponse,
    summary="Xem thống kê tổng quan Data Lake",
    description="Báo cáo số lượng bản ghi theo từng zone trong Data Lake, phân bổ intent và trạng thái xử lý.",
    dependencies=[Depends(require_permission("admin_dataset:read"))],
)
def get_dataset_summary(db: Session = Depends(get_db)):
    return AdminDatasetService.get_summary(db=db)


@router.get(
    "/export",
    response_model=List[Dict[str, Any]],
    summary="Xuất dữ liệu Dataset phục vụ AI Evaluation / Research",
    description="Trích xuất các mẫu dữ liệu hợp lệ kèm nhãn intent, entities và tham chiếu audio để đánh giá mô hình.",
    dependencies=[Depends(require_permission("admin_dataset:export"))],
)
def export_dataset(
    intent: Optional[str] = Query(None, description="Lọc theo intent cụ thể"),
    status: Optional[str] = Query("SUCCESS", description="Trạng thái mẫu"),
    limit: int = Query(500, ge=1, le=2000, description="Số lượng mẫu tối đa"),
    db: Session = Depends(get_db),
):
    return AdminDatasetService.export_dataset(
        db=db,
        intent=intent,
        status_filter=status,
        limit=limit,
    )


@router.get(
    "/{id}",
    response_model=AdminDatasetDetailResponse,
    summary="Xem chi tiết một bản ghi Dataset trong Data Lake",
    description="Xem đầy đủ dữ liệu thô, kết quả AI, hiệu chỉnh của người dùng, liên kết giao dịch và vị trí lưu trữ trong Data Lake.",
    dependencies=[Depends(require_permission("admin_dataset:read"))],
)
def get_dataset_detail(id: int, db: Session = Depends(get_db)):
    return AdminDatasetService.get_dataset_detail(db=db, voice_id=id)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminDatasetIngestResponse,
    summary="Ingest bản ghi Voice Processing vào Data Lake",
    description="Kích hoạt quá trình snapshot lưu trữ bản ghi vào các vùng Raw, Processed, Feedback và Dataset trong Data Lake.",
    dependencies=[Depends(require_permission("admin_dataset:manage"))],
)
def ingest_voice_record_to_lake(data: DatasetIngestRequest, db: Session = Depends(get_db)):
    return AdminDatasetService.ingest_voice_record(db=db, voice_id=data.voice_id)
