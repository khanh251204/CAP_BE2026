from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AdminDatasetPagination(BaseModel):
    page: int = Field(..., description="Trang hiện tại (1-based)")
    limit: int = Field(..., description="Số bản ghi trên mỗi trang")
    total: int = Field(..., description="Tổng số bản ghi thỏa điều kiện")
    total_pages: int = Field(..., description="Tổng số trang")


class AdminDatasetItem(BaseModel):
    id: int = Field(..., description="ID bản ghi Data Lake / VoiceRecord")
    voice_record_id: int = Field(..., description="ID Voice Record gốc")
    data_type: str = Field(..., description="Phân loại dữ liệu: RAW, PROCESSED, FEEDBACK, DATASET")
    source_type: str = Field(..., description="Nguồn dữ liệu: VOICE_PIPELINE, MOBILE, WEB")
    transcript: Optional[str] = Field(None, description="Chuỗi văn bản STT nhận dạng")
    intent: Optional[str] = Field(None, description="Mã intent phân loại")
    confidence: Optional[float] = Field(None, description="Độ tin cậy STT")
    status: str = Field(..., description="Trạng thái xử lý: SUCCESS, FAILED, PROCESSING, REVIEW")
    has_correction: bool = Field(False, description="Có dữ liệu hiệu chỉnh từ người dùng không")
    storage_path: Optional[str] = Field(None, description="Đường dẫn snapshot lưu trữ trong Data Lake")
    created_at: Optional[datetime] = Field(None, description="Thời điểm khởi tạo bản ghi")


class AdminDatasetListResponse(BaseModel):
    items: List[AdminDatasetItem] = Field(..., description="Danh sách bản ghi dataset trong Data Lake")
    pagination: AdminDatasetPagination = Field(..., description="Thông tin phân trang")


class AdminDatasetStorageMeta(BaseModel):
    storage_type: str = Field("LOCAL_FS", description="Loại lưu trữ Data Lake: LOCAL_FS hoặc OBJECT_STORAGE")
    raw_path: Optional[str] = Field(None, description="Đường dẫn lưu trữ Zone Raw")
    processed_path: Optional[str] = Field(None, description="Đường dẫn lưu trữ Zone Processed")
    feedback_path: Optional[str] = Field(None, description="Đường dẫn lưu trữ Zone Feedback / Correction")
    dataset_path: Optional[str] = Field(None, description="Đường dẫn lưu trữ Zone Dataset")
    ingested_at: Optional[datetime] = Field(None, description="Thời điểm ingest vào Data Lake")


class AdminDatasetDetailResponse(BaseModel):
    id: int = Field(..., description="ID bản ghi dataset")
    voice_record_id: int = Field(..., description="ID Voice Record liên kết")
    data_type: str = Field(..., description="Phân loại: RAW, PROCESSED, FEEDBACK, DATASET")
    source_type: str = Field(..., description="Nguồn dữ liệu: VOICE_PIPELINE")
    user_id: Optional[int] = Field(None, description="ID người dùng")
    user_name: Optional[str] = Field(None, description="Họ tên người dùng")
    audio_url: Optional[str] = Field(None, description="URL stream/nghe file âm thanh bảo mật")
    transcript: Optional[str] = Field(None, description="Văn bản nhận dạng giọng nói")
    intent: Optional[str] = Field(None, description="Intent AI phân loại")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Các thực thể trích xuất động")
    confidence: Dict[str, Optional[float]] = Field(default_factory=dict, description="Các chỉ số độ tin cậy thực tế")
    validation: Dict[str, Any] = Field(default_factory=dict, description="Kết quả kiểm tra nghiệp vụ backend")
    correction: Optional[Dict[str, Any]] = Field(None, description="Hiệu chỉnh từ người dùng (nếu có)")
    transaction: Optional[Dict[str, Any]] = Field(None, description="Giao dịch phát sinh (nếu có)")
    processing: Dict[str, Any] = Field(default_factory=dict, description="Thông tin metadata tiến trình xử lý kỹ thuật")
    storage: AdminDatasetStorageMeta = Field(..., description="Thông tin metadata lưu trữ trong Data Lake")
    created_at: Optional[datetime] = Field(None, description="Thời điểm khởi tạo")


class AdminDatasetSummaryResponse(BaseModel):
    total_records: int = Field(..., description="Tổng số bản ghi trong Data Lake")
    raw_count: int = Field(..., description="Số bản ghi có dữ liệu thô (Audio/Source)")
    processed_count: int = Field(..., description="Số bản ghi đã qua xử lý AI (Transcript/Intent/Entities)")
    correction_count: int = Field(..., description="Số bản ghi có hiệu chỉnh người dùng (Human-in-the-loop)")
    dataset_count: int = Field(..., description="Số mẫu hợp lệ sẵn sàng cho AI Dataset / Evaluation")
    intents_breakdown: Dict[str, int] = Field(default_factory=dict, description="Phân bổ số lượng mẫu theo từng intent")
    status_breakdown: Dict[str, int] = Field(default_factory=dict, description="Phân bổ số lượng theo trạng thái")


class AdminDatasetIngestResponse(BaseModel):
    success: bool = Field(..., description="Kết quả ingestion vào Data Lake")
    voice_record_id: int = Field(..., description="ID bản ghi được ingest")
    storage_paths: Dict[str, str] = Field(default_factory=dict, description="Đường dẫn các snapshot lưu trữ tại các zone")
    message: str = Field(..., description="Thông điệp kết quả")
