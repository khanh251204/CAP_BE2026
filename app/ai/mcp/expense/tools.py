from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CreateExpenseInput(BaseModel):
    amount: float = Field(..., gt=0, description="Số tiền chi phí (bắt buộc, > 0)")
    category_name: Optional[str] = Field(None, description="Tên danh mục chi phí (tiền điện, tiền nước, mặt bằng...)")
    category_id: Optional[int] = Field(None, description="ID danh mục chi phí nếu có")
    account_id: Optional[int] = Field(None, description="Tài khoản nguồn chi tiền (nếu có)")
    note: Optional[str] = Field(None, description="Ghi chú chi phí")
    payment_status: Optional[str] = Field("PAID", description="Trạng thái thanh toán ('PAID', 'PENDING', 'PARTIAL')")
    date: Optional[str] = Field(None, description="Ngày phát sinh chi phí YYYY-MM-DD")
    input_text: Optional[str] = Field(None, description="Nội dung người dùng nhập/nói")


class CreateExpenseOutput(BaseModel):
    success: bool
    status: str
    transaction_id: int
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    amount: float
    payment_status: str
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    transaction_date: Optional[str] = None
    note: Optional[str] = None
    message: str
