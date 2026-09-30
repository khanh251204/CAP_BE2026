from pydantic import BaseModel, Field
from typing import Optional


class AnalysisRequest(BaseModel):
    text: str = Field(..., description="Văn bản hoặc câu nói giao dịch cần phân tích")
    session_id: Optional[str] = Field(None, description="ID phiên làm việc nếu có")
    voice_id: Optional[int] = Field(None, description="ID bản ghi Voice_Record từ bước STT")
    input_method: Optional[str] = Field(None, description="Phương thức nhập: VOICE hoặc MANUAL")
