from pydantic import BaseModel, Field
from typing import Optional


class STTResponse(BaseModel):
    success: bool
    code: str = Field(..., description="STT_SUCCESS, NO_SPEECH, AUDIO_INVALID, AUDIO_TOO_SHORT, SPEAKER_NOT_VERIFIED, STT_FAILED")
    text: Optional[str] = Field(None, description="Văn bản nhận diện được nếu thành công")
    message: Optional[str] = Field(None, description="Thông điệp mô tả lỗi nếu thất bại")
