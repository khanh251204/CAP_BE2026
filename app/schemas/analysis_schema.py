from pydantic import BaseModel, Field
from typing import Optional


class AnalysisRequest(BaseModel):
    text: str = Field(..., description="Văn bản hoặc câu nói giao dịch cần phân tích")
    session_id: Optional[str] = Field(None, description="ID phiên làm việc nếu có")
    voice_id: Optional[int] = Field(None, description="ID bản ghi Voice_Record từ bước STT")
    input_method: Optional[str] = Field(None, description="Phương thức nhập: VOICE hoặc MANUAL")


class FormDraftRequest(BaseModel):
    """Nhập bằng biểu mẫu: app gửi sẵn nghiệp vụ + trường đã chọn (không qua LLM)."""

    intent: str = Field(..., description="ban_hang, mua_hang, chi_phi, khach_ghi_no, thu_no_khach, ghi_no_nha_cung_cap, tra_no_nha_cung_cap")
    product: Optional[str] = Field(None, max_length=200, description="Tên sản phẩm")
    product_id: Optional[int] = Field(None, description="ID sản phẩm đã chọn từ danh sách")
    quantity: Optional[float] = Field(None, description="Số lượng")
    unit: Optional[str] = Field(None, max_length=50, description="Đơn vị")
    price: Optional[float] = Field(None, description="Đơn giá, hoặc số tiền với chi phí / thu - trả nợ")
    total_price: Optional[float] = Field(None, description="Tổng tiền nếu người dùng nhập tổng thay vì đơn giá")
    customer: Optional[str] = Field(None, max_length=200)
    customer_id: Optional[int] = None
    supplier: Optional[str] = Field(None, max_length=200)
    supplier_id: Optional[int] = None
    category: Optional[str] = Field(None, max_length=200, description="Khoản chi (chi_phi)")
    payment: Optional[str] = Field(None, description="cash | transfer | card | debt")
    note: Optional[str] = Field(None, max_length=300)
    date: Optional[str] = Field(None, description="YYYY-MM-DD, mặc định hôm nay")
