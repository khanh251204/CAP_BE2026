from typing import Optional

from pydantic import BaseModel, Field


class UpdateDebtRequest(BaseModel):
    """Sửa khoản nợ nhập tay: chỉ đổi đối tác (cùng chiều nợ) hoặc số tiền gốc (khi chưa có thanh toán)."""
    customer_id: Optional[int] = Field(None, ge=1, description="Khách hàng mới (chỉ nợ RECEIVABLE)")
    supplier_id: Optional[int] = Field(None, ge=1, description="Nhà cung cấp mới (chỉ nợ PAYABLE)")
    original_amount: Optional[float] = Field(None, gt=0, description="Số tiền nợ gốc mới (chỉ khi chưa có thanh toán)")
