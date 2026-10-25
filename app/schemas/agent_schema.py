from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class CorrectedItemSchema(BaseModel):
    """
    Chi tiết từng mặt hàng trong giao dịch được người dùng hiệu chỉnh.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    product_id: Optional[int] = Field(None, description="ID sản phẩm nếu có")
    product_name: Optional[str] = Field(None, alias="product", description="Tên sản phẩm")
    quantity: Optional[float] = Field(None, gt=0, description="Số lượng")
    unit: Optional[str] = Field(None, description="Đơn vị tính (lon, thùng, bao...)")
    unit_price: Optional[float] = Field(None, ge=0, alias="price", description="Đơn giá")
    subtotal: Optional[float] = Field(None, description="Thành tiền do client gửi (Backend sẽ tính lại, không tin tưởng)")


class CorrectedTransactionSchema(BaseModel):
    """
    Bản giao dịch do người dùng sửa trên giao diện trước khi xác nhận.
    Hỗ trợ cả dạng đơn hàng 1 sản phẩm phẳng và danh sách nhiều sản phẩm.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    intent: Optional[str] = Field(None, description="Tên intent (ban_hang, mua_hang, chi_phi...)")

    # Trường hợp đơn hàng 1 sản phẩm
    product_id: Optional[int] = Field(None, description="ID sản phẩm")
    product_name: Optional[str] = Field(None, alias="product", description="Tên sản phẩm")
    quantity: Optional[float] = Field(None, description="Số lượng")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    unit_price: Optional[float] = Field(None, alias="price", description="Đơn giá")

    # Trường hợp danh sách sản phẩm (items / products)
    items: Optional[List[CorrectedItemSchema]] = Field(None, description="Danh sách sản phẩm")

    # Đối tác
    customer_id: Optional[int] = Field(None, description="ID khách hàng")
    customer_name: Optional[str] = Field(None, alias="customer", description="Tên khách hàng")
    supplier_id: Optional[int] = Field(None, description="ID nhà cung cấp")
    supplier_name: Optional[str] = Field(None, alias="supplier", description="Tên nhà cung cấp")

    # Thanh toán & Công nợ
    payment_status: Optional[str] = Field(None, alias="payment", description="Trạng thái thanh toán (PAID, PARTIAL, PENDING)")
    amount_paid: Optional[float] = Field(None, ge=0, description="Số tiền đã trả")
    total_amount: Optional[float] = Field(None, description="Tổng tiền (Backend sẽ tính lại)")
    amount: Optional[float] = Field(None, description="Số tiền (cho chi phí / thu chi)")

    # Phân loại & Tài khoản
    category_id: Optional[int] = Field(None, description="ID danh mục thu chi")
    category_name: Optional[str] = Field(None, alias="category", description="Tên danh mục thu chi")
    account_id: Optional[int] = Field(None, description="Tài khoản thanh toán")
    note: Optional[str] = Field(None, description="Ghi chú giao dịch")
    date: Optional[str] = Field(None, description="Ngày giao dịch")


class AgentConfirmRequest(BaseModel):
    """
    Body tùy chọn cho endpoint POST /api/v1/agent/pending-action/confirmation.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    session_id: Optional[str] = Field(None, description="ID phiên làm việc (nếu lưu theo session_id)")
    voice_id: Optional[int] = Field(None, description="ID bản ghi âm Voice_Record")
    input_method: Optional[str] = Field(None, description="Phương thức nhập: VOICE hoặc MANUAL")
    corrected_transaction: Optional[CorrectedTransactionSchema] = Field(
        None,
        description="Bản giao dịch người dùng đã hiệu chỉnh trên UI. Nếu không truyền, dùng bản gốc từ session."
    )
