from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List, Set, Dict
from datetime import datetime


class IntentTypeEnum(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANFER = "TRANFER"  # Theo đúng docs/erd_new.md và DB enum name
    REFUND = "REFUND"
    DEBT = "DEBT"
    NONE = "NONE"


class IntentNameEnum(str, Enum):
    ban_hang = "ban_hang"
    mua_hang = "mua_hang"
    ghi_no_khach_hang = "ghi_no_khach_hang"
    thu_no_khach_hang = "thu_no_khach_hang"
    ghi_no_nha_cung_cap = "ghi_no_nha_cung_cap"
    tra_no_nha_cung_cap = "tra_no_nha_cung_cap"
    tra_no_cung_cap = "tra_no_cung_cap"
    chi_tien = "chi_tien"
    hang_hong = "hang_hong"
    kiem_kho = "kiem_kho"
    bao_cao = "bao_cao"
    chot_so = "chot_so"


VALID_INTENT_TYPE_COMBINATIONS: Dict[str, Set[str]] = {
    "ban_hang": {"INCOME"},
    "mua_hang": {"EXPENSE"},
    "chi_tien": {"EXPENSE"},
    "hang_hong": {"EXPENSE"},
    "ghi_no_khach_hang": {"DEBT"},
    "ghi_no_nha_cung_cap": {"DEBT"},
    "thu_no_khach_hang": {"INCOME", "DEBT"},
    "tra_no_nha_cung_cap": {"EXPENSE", "DEBT"},
    "tra_no_cung_cap": {"EXPENSE", "DEBT"},
    "kiem_kho": {"NONE"},
    "bao_cao": {"NONE"},
    "chot_so": {"NONE"},
}


class TransactionQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="Số trang (bắt đầu từ 1)")
    limit: int = Field(default=10, ge=1, le=100, description="Số lượng bản ghi trên một trang")
    intent_type: Optional[IntentTypeEnum] = Field(
        default=None,
        description="Lọc theo loại intent (INCOME, EXPENSE, DEBT, TRANFER, REFUND, NONE theo docs/erd_new.md)"
    )
    intent: Optional[IntentNameEnum] = Field(
        default=None,
        description="Lọc theo tên intent cụ thể chuẩn theo docs/erd_new.md"
    )

    @model_validator(mode="after")
    def validate_intent_combination(self):
        if self.intent is not None and self.intent_type is not None:
            allowed_types = VALID_INTENT_TYPE_COMBINATIONS.get(self.intent.value)
            if allowed_types and self.intent_type.value not in allowed_types:
                raise ValueError(
                    f"Intent '{self.intent.value}' không phù hợp với intent_type '{self.intent_type.value}'. "
                    f"Các intent_type hợp lệ: {sorted(list(allowed_types))}"
                )
        return self


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