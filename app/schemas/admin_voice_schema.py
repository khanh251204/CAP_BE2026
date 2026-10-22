from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AdminVoicePagination(BaseModel):
    page: int = Field(..., description="Trang hiện tại (1-based)")
    limit: int = Field(..., description="Số bản ghi trên mỗi trang")
    total: int = Field(..., description="Tổng số bản ghi thỏa mãn điều kiện lọc")
    total_pages: int = Field(..., description="Tổng số trang")


class AdminVoiceListItem(BaseModel):
    id: int = Field(..., description="ID bản ghi xử lý giọng nói (voice_id)")
    user_id: Optional[int] = Field(None, description="ID người dùng")
    user_name: Optional[str] = Field(None, description="Tên người dùng")
    transcript: Optional[str] = Field(None, description="Chuỗi văn bản STT nhận diện được")
    intent: Optional[str] = Field(None, description="Mã intent nhận diện")
    confidence: Optional[float] = Field(None, description="Độ tin cậy STT")
    status: str = Field(..., description="Trạng thái xử lý: SUCCESS, FAILED, PROCESSING, REVIEW")
    transaction_id: Optional[int] = Field(None, description="ID giao dịch tài chính liên kết (nếu có)")
    audio_url: Optional[str] = Field(None, description="URL stream/nghe file ghi âm")
    processing_time_ms: Optional[int] = Field(None, description="Thời gian xử lý tính bằng mili-giây (ms)")
    created_at: Optional[datetime] = Field(None, description="Thời gian khởi tạo bản ghi")


class AdminVoiceListResponse(BaseModel):
    items: List[AdminVoiceListItem] = Field(..., description="Danh sách lịch sử xử lý voice")
    pagination: AdminVoicePagination = Field(..., description="Thông tin phân trang")


class AdminVoiceDetailUser(BaseModel):
    id: Optional[int] = Field(None, description="ID người dùng")
    name: Optional[str] = Field(None, description="Họ và tên người dùng")


class AdminVoiceDetailAudio(BaseModel):
    url: Optional[str] = Field(None, description="URL stream/nghe file ghi âm bảo mật")
    duration: Optional[float] = Field(None, description="Thời lượng âm thanh tính bằng giây")


class AdminVoiceDetailAiResult(BaseModel):
    intent: Optional[str] = Field(None, description="Intent AI phân loại")
    confidence: Optional[float] = Field(None, description="Độ tin cậy AI/STT")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Các thực thể trích xuất (product, quantity, unit, price...)")


class AdminVoiceDetailValidation(BaseModel):
    status: str = Field("VALID", description="Trạng thái kiểm tra nghiệp vụ (VALID, INVALID, PENDING)")
    errors: List[str] = Field(default_factory=list, description="Danh sách lỗi validation nghiệp vụ (nếu có)")


class AdminVoiceDetailTransaction(BaseModel):
    id: Optional[int] = Field(None, description="ID giao dịch phát sinh")
    status: Optional[str] = Field(None, description="Trạng thái giao dịch (PAID, PARTIAL, PENDING hoặc CREATED)")


class AdminVoiceDetailProcessing(BaseModel):
    status: str = Field(..., description="Trạng thái xử lý hệ thống: SUCCESS, FAILED, PROCESSING, REVIEW")
    processing_time_ms: Optional[int] = Field(None, description="Thời gian xử lý tính bằng mili-giây (ms)")
    error_message: Optional[str] = Field(None, description="Thông điệp lỗi nếu xử lý thất bại")


class AdminVoiceDetailResponse(BaseModel):
    id: int = Field(..., description="ID bản ghi xử lý giọng nói")
    user: Optional[AdminVoiceDetailUser] = Field(None, description="Thông tin người dùng")
    audio: Optional[AdminVoiceDetailAudio] = Field(None, description="Thông tin file âm thanh")
    transcript: Optional[str] = Field(None, description="Nội dung nhận dạng giọng nói")
    ai_result: AdminVoiceDetailAiResult = Field(..., description="Kết quả phân tích từ AI (intent, confidence, entities)")
    validation: AdminVoiceDetailValidation = Field(..., description="Kết quả kiểm tra nghiệp vụ")
    correction: Optional[Dict[str, Any]] = Field(None, description="Thông tin người dùng hiệu chỉnh kết quả AI (nếu có)")
    transaction: Optional[AdminVoiceDetailTransaction] = Field(None, description="Giao dịch tạo ra từ voice (nếu có)")
    processing: AdminVoiceDetailProcessing = Field(..., description="Thông tin tiến trình xử lý kỹ thuật")
    created_at: Optional[datetime] = Field(None, description="Thời điểm khởi tạo")
    updated_at: Optional[datetime] = Field(None, description="Thời điểm cập nhật sau cùng")


# ==============================================================================
# AI RESULT RESPONSE SCHEMAS
# ==============================================================================

class AdminVoiceAiResultTranscript(BaseModel):
    text: Optional[str] = Field(None, description="Văn bản nhận dạng từ giọng nói")


class AdminVoiceAiResultIntent(BaseModel):
    name: Optional[str] = Field(None, description="Mã intent phân loại (ban_hang, chi_tien...)")
    display_name: Optional[str] = Field(None, description="Tên hiển thị intent nếu có")


class AdminVoiceAiResultConfidence(BaseModel):
    intent: Optional[float] = Field(None, description="Độ tin cậy của intent (nếu có nguồn chuẩn)")
    entity: Optional[float] = Field(None, description="Độ tin cậy của thực thể (nếu có nguồn chuẩn)")
    overall: Optional[float] = Field(None, description="Độ tin cậy tổng thể (nếu có công thức chuẩn)")
    stt: Optional[float] = Field(None, description="Độ tin cậy nhận diện STT từ Voice_Record.confidence")


class AdminVoiceAiResultValidation(BaseModel):
    status: str = Field("valid", description="Trạng thái kiểm tra nghiệp vụ: valid, invalid, pending")
    errors: List[str] = Field(default_factory=list, description="Danh sách lỗi validation")
    warnings: List[str] = Field(default_factory=list, description="Danh sách cảnh báo validation")


class AdminVoiceAiResultTransaction(BaseModel):
    id: int = Field(..., description="ID giao dịch tài chính liên kết")
    status: Optional[str] = Field(None, description="Trạng thái thanh toán (PAID, PARTIAL, PENDING)")
    total_amount: Optional[float] = Field(None, description="Tổng số tiền giao dịch")
    transaction_date: Optional[datetime] = Field(None, description="Thời điểm giao dịch phát sinh")


class AdminVoiceAiResultProcessing(BaseModel):
    status: str = Field(..., description="Trạng thái xử lý: success, failed, processing, review")
    processing_time_ms: Optional[int] = Field(None, description="Thời gian xử lý (ms)")
    provider: Optional[str] = Field(None, description="Nhà cung cấp dịch vụ AI/STT (Groq/Whisper)")
    model: Optional[str] = Field(None, description="Model AI sử dụng")
    model_version: Optional[str] = Field(None, description="Phiên bản model AI sử dụng")
    prompt_version: Optional[str] = Field(None, description="Phiên bản prompt AI sử dụng")
    pipeline_version: Optional[str] = Field(None, description="Phiên bản pipeline xử lý AI")
    error_message: Optional[str] = Field(None, description="Thông điệp lỗi nếu thất bại")


class AdminVoiceAiResultResponse(BaseModel):
    voice_record_id: int = Field(..., description="ID bản ghi xử lý giọng nói")
    transcript: Optional[AdminVoiceAiResultTranscript] = Field(None, description="Văn bản nhận dạng STT")
    intent: Optional[AdminVoiceAiResultIntent] = Field(None, description="Intent AI phân loại")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Các thực thể AI trích xuất động")
    confidence: AdminVoiceAiResultConfidence = Field(..., description="Độ tin cậy thực tế (null nếu không có nguồn chuẩn)")
    validation: AdminVoiceAiResultValidation = Field(..., description="Kết quả kiểm tra nghiệp vụ backend")
    correction: Optional[Dict[str, Any]] = Field(None, description="User correction nếu có sự thay đổi so với AI result")
    transaction: Optional[AdminVoiceAiResultTransaction] = Field(None, description="Giao dịch được tạo từ AI result (nếu có)")
    processing: AdminVoiceAiResultProcessing = Field(..., description="Thông tin tiến trình xử lý kỹ thuật")


class AdminUserCorrectionItem(BaseModel):
    id: int = Field(..., description="ID bản ghi hiệu chỉnh")
    user_id: Optional[int] = Field(None, description="ID người dùng")
    voice_record_id: Optional[int] = Field(None, description="ID bản ghi voice liên kết")
    transaction_id: Optional[int] = Field(None, description="ID giao dịch tài chính liên kết")
    correction_type: str = Field(..., description="Loại hiệu chỉnh (MANUAL_EDIT, CONFIRM_NO_CHANGE...)")
    original_ai_result: Dict[str, Any] = Field(default_factory=dict, description="Kết quả AI ban đầu")
    corrected_result: Dict[str, Any] = Field(default_factory=dict, description="Kết quả sau khi người dùng sửa")
    diff: Dict[str, Any] = Field(default_factory=dict, description="Sai khác chi tiết")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata bổ sung")
    created_at: Optional[datetime] = Field(None, description="Thời điểm ghi nhận hiệu chỉnh")


class AdminUserCorrectionListResponse(BaseModel):
    items: List[AdminUserCorrectionItem] = Field(..., description="Danh sách bản ghi hiệu chỉnh")
    pagination: AdminVoicePagination = Field(..., description="Thông tin phân trang")


