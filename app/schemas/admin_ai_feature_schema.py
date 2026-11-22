from typing import List, Optional

from pydantic import BaseModel, Field


class AdminAIPlanUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tên gói hiển thị (VD: Gói Cơ Bản 50K)")
    price_vnd: int = Field(0, ge=0, description="Giá gói (VNĐ)")
    description: str = Field("", max_length=500, description="Mô tả ngắn về gói")
    allowed_intents: Optional[List[str]] = Field(
        None,
        description="Danh sách mã intent được phép (VD: ['ban_hang', 'mua_hang']). null = mở toàn bộ 17 intents; [] = khóa AI.",
    )
    allow_multi_item: bool = Field(True, description="Cho phép tách nhiều sản phẩm trong 1 câu nói")
    allow_ocr: bool = Field(True, description="Cho phép quét hóa đơn nhập hàng (OCR)")


class AdminUserAIFeatureUpdateRequest(BaseModel):
    plan_code: Optional[str] = Field(
        None,
        max_length=64,
        description="Mã gói muốn gán (VD: 'basic_50k', 'standard', 'pro', 'locked'). Để trống nếu tùy chỉnh riêng từng intent.",
    )
    allowed_intents: Optional[List[str]] = Field(
        None,
        description="Ghi đè danh sách intent được phép. Chỉ áp dụng nếu trường này được gửi trong JSON body.",
    )
    allow_multi_item: Optional[bool] = Field(
        None,
        description="Ghi đè quyền xử lý nhiều sản phẩm trong 1 câu.",
    )
    allow_ocr: Optional[bool] = Field(
        None,
        description="Ghi đè quyền quét hóa đơn OCR.",
    )
    note: Optional[str] = Field(None, max_length=255, description="Ghi chú của admin (VD: 'Đã thanh toán gói 50k')")


class AdminBulkAssignAIFeatureRequest(AdminUserAIFeatureUpdateRequest):
    user_ids: List[int] = Field(..., min_length=1, max_length=200, description="Danh sách user_id cần áp dụng")
