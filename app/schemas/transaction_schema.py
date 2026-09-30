from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TransactionDetailCreate(BaseModel):
    """
    Schema chi tiết hàng hóa (Transaction_Detail) theo docs/erd.md
    """
    product_id: int = Field(..., description="ID sản phẩm (FK -> Product)")
    product_name: Optional[str] = Field(None, description="Tên sản phẩm snapshot tại thời điểm giao dịch")
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
    voice_id: Optional[int] = Field(None, description="ID bản ghi Voice_Record nếu giao dịch xuất phát từ giọng nói")

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


# ==========================================
# RESPONSE SCHEMAS CHO TRANSACTION (docs/erd.md)
# ==========================================
class TransactionAccountBrief(BaseModel):
    account_id: int
    account_name: Optional[str] = None
    name: Optional[str] = None
    account_type: Optional[str] = None


class TransactionPartnerBrief(BaseModel):
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    customer_name: Optional[str] = None
    supplier_name: Optional[str] = None
    name: Optional[str] = None


class TransactionResponseItem(BaseModel):
    transaction_id: int
    user_id: int
    intent_id: Optional[int] = None
    intent: Optional[str] = Field(None, description="Tên intent (10 intent docs/erd.md)")
    intent_name: Optional[str] = Field(None, description="Tên intent")
    intent_type: Optional[str] = Field(None, description="Loại intent theo docs/erd.md (INCOME, EXPENSE, DEBT, TRANFER, REFUND, NONE)")
    type: Optional[str] = Field(None, description="Tương đương intent_type để FE tiện phân loại thu/chi/nợ")
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    account: Optional[TransactionAccountBrief] = None
    customer: Optional[TransactionPartnerBrief] = None
    supplier: Optional[TransactionPartnerBrief] = None
    total_amount: float
    payment_status: Optional[str] = None
    input_method: Optional[str] = None
    input_text: Optional[str] = None
    note: Optional[str] = None
    transaction_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    details: List[TransactionDetailResponse] = Field(default_factory=list)


class TransactionListResponse(BaseModel):
    items: List[TransactionResponseItem]
    page: int
    limit: int
    total: int
    total_pages: int