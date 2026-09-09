from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TransactionDetailCreate(BaseModel):
    """
    Schema chi tiết hàng hóa (Transaction_Detail) theo docs/erd.md
    """
    product_id: int = Field(..., description="ID sản phẩm (FK -> Product)")
    quantity: float = Field(..., gt=0, description="Số lượng")
    unit: str = Field(..., description="Đơn vị tính (hộp, lốc, chai...)")
    unit_price: float = Field(..., ge=0, description="Đơn giá")
    subtotal: Optional[float] = Field(None, description="Thành tiền = quantity * unit_price")


class TransactionDetailResponse(BaseModel):
    detail_id: int
    product_id: int
    product_name: Optional[str] = None
    image: Optional[str] = None
    quantity: float
    unit: str
    unit_price: float
    subtotal: float


class TransactionCreateRequest(BaseModel):
    """
    Request tạo giao dịch (Transaction) đối chiếu theo docs/erd.md:
    
    1. Chế độ Direct Model (theo chuẩn ERD):
       - intent_id: FK -> Intent
       - category_id: FK -> Category
       - account_id: FK -> Account
       - customer_id: FK -> Customer
       - supplier_id: FK -> Supplier
       - total_amount: Tổng tiền giao dịch
       - payment_status: 'PAID' | 'PARTIAL' | 'PENDING'
       - input_method: 'VOICE' | 'MANUAL'
       - input_text: Nội dung văn bản
       - note: Ghi chú giao dịch
       - transaction_date: Thời gian phát sinh giao dịch
       - details: Danh sách chi tiết dòng hàng (Transaction_Detail)
    
    2. Chế độ Flat NLP / Quick Form (tương thích ngược cho FE gửi text hoặc entities):
       - text, intent, type, product, price, quantity, unit, customer, supplier, date, payment
    """
    # === Các trường chuẩn theo Model & ERD ===
    intent_id: Optional[int] = Field(None, description="FK -> Intent")
    category_id: Optional[int] = Field(None, description="FK -> Category")
    account_id: Optional[int] = Field(None, description="FK -> Account")
    customer_id: Optional[int] = Field(None, description="FK -> Customer")
    supplier_id: Optional[int] = Field(None, description="FK -> Supplier")
    total_amount: Optional[float] = Field(None, ge=0, description="Tổng giá trị giao dịch")
    payment_status: Optional[str] = Field(
        None,
        description="Trạng thái thanh toán theo ERD: 'PAID', 'PARTIAL', 'PENDING'"
    )
    input_method: Optional[str] = Field(
        "MANUAL",
        description="Phương thức nhập theo ERD: 'VOICE', 'MANUAL'"
    )
    input_text: Optional[str] = Field(None, description="Văn bản gốc / text đầu vào")
    note: Optional[str] = Field(None, description="Ghi chú giao dịch")
    transaction_date: Optional[datetime] = Field(None, description="Ngày giao dịch")

    # Danh sách chi tiết hàng hóa (1-N Transaction_Detail)
    details: Optional[List[TransactionDetailCreate]] = Field(
        None,
        description="Chi tiết từng dòng sản phẩm"
    )

    # === Các trường phẳng tương thích ngược (Flat NLP / Voice parsing) ===
    text: Optional[str] = Field(None, description="Câu văn bản nhập vào")
    intent: Optional[str] = Field(None, description="Tên intent (ban_hang, nhap_hang...)")
    type: Optional[str] = Field(None, description="Loại giao dịch (INCOME, EXPENSE...)")
    product: Optional[str] = Field(None, description="Tên sản phẩm đơn lẻ")
    price: Optional[float] = Field(None, description="Đơn giá hoặc số tiền")
    quantity: Optional[float] = Field(None, description="Số lượng")
    unit: Optional[str] = Field(None, description="Đơn vị tính")
    customer: Optional[str] = Field(None, description="Tên khách hàng")
    supplier: Optional[str] = Field(None, description="Tên nhà cung cấp")
    date: Optional[str] = Field(None, description="Ngày diễn giải dạng text")
    payment: Optional[str] = Field(None, description="Phương thức thanh toán dạng text")