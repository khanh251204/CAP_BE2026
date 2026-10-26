from typing import Optional, List
from pydantic import BaseModel, Field


class GhiNoKhachHangInput(BaseModel):
    customer_id: Optional[int] = Field(None, description="ID khách hàng cần ghi nợ")
    customer_name: Optional[str] = Field(None, description="Tên khách hàng (dùng khi chưa có customer_id)")
    new_customer: bool = Field(False, description="True: người dùng đã đồng ý tạo khách hàng mới nếu chưa tồn tại")
    original_amount: float = Field(..., gt=0, description="Số tiền gốc còn nợ, tương ứng cột Debt.original_amount trong erd.md")
    transaction_id: Optional[int] = Field(
        None,
        description=(
            "ID giao dịch gốc nếu đã có (ví dụ vừa tạo qua ban_hang). "
            "Nếu không truyền, DebtService sẽ tự tạo 1 Transaction rỗng "
            "(payment_status='PENDING') để thỏa FK bắt buộc Debt.transaction_id theo erd.md."
        ),
    )
    note: Optional[str] = Field(None, description="Câu người dùng nhập/nói, lưu vào Transaction.input_text")
    input_method: Optional[str] = Field("MANUAL", description="Phương thức nhập theo ERD: 'VOICE' | 'MANUAL'")


class GhiNoKhachHangOutput(BaseModel):
    debt_id: int
    status: str          # 'UNPAID' | 'PARTIAL' | 'PAID' — theo enum Debt.status trong erd.md
    remaining_debt: float
    transaction_id: Optional[int] = None


class ThuNoKhachHangInput(BaseModel):
    account_id: int = Field(..., description="Tài khoản/ví nhận tiền, cột Account.account_id")
    amount: float = Field(..., gt=0, description="Số tiền khách vừa trả")
    debt_id: Optional[int] = Field(None, description="Chỉ truyền khi biết rõ khoản nợ cụ thể cần thu")
    customer_id: Optional[int] = Field(None, description="Chỉ truyền khi thu theo tổng tiền, để hệ thống tự phân bổ FIFO")
    input_method: Optional[str] = Field("MANUAL", description="Phương thức nhập theo ERD: 'VOICE' | 'MANUAL'")

    def model_post_init(self, __context) -> None:
        if not self.debt_id and not self.customer_id:
            raise ValueError("Phải có debt_id hoặc customer_id")
        if self.debt_id and self.customer_id:
            raise ValueError("Chỉ được truyền MỘT trong hai: debt_id hoặc customer_id, không truyền cả hai")


class DebtAllocationItem(BaseModel):
    debt_id: int
    amount_applied: float
    remaining_debt: float
    debt_status: str


class ThuNoKhachHangOutput(BaseModel):
    # Có mặt ở cả 2 chế độ
    amount_collected: float
    # Chế độ đích danh (debt_id) — có giá trị, còn lại None
    debt_id: Optional[int] = None
    remaining_debt: Optional[float] = None
    debt_status: Optional[str] = None
    # Chế độ FIFO (customer_id) — có giá trị, còn lại None
    customer_id: Optional[int] = None
    total_remaining_before: Optional[float] = None
    total_remaining_after: Optional[float] = None
    debts: Optional[List[DebtAllocationItem]] = None


# ============================================================
# CÔNG NỢ NHÀ CUNG CẤP (SUPPLIER DEBT)
# ============================================================

class GhiNoNhaCungCapInput(BaseModel):
    supplier_id: Optional[int] = Field(None, description="ID nhà cung cấp cần ghi nợ")
    supplier_name: Optional[str] = Field(None, description="Tên nhà cung cấp (dùng khi chưa có supplier_id)")
    new_supplier: bool = Field(False, description="True: người dùng đã đồng ý tạo nhà cung cấp mới nếu chưa tồn tại")
    original_amount: float = Field(..., gt=0, description="Số tiền gốc còn nợ, tương ứng cột Debt.original_amount trong erd.md")
    transaction_id: Optional[int] = Field(
        None,
        description=(
            "ID giao dịch gốc nếu đã có (ví dụ vừa tạo qua nhap_hang). "
            "Nếu không truyền, DebtService sẽ tự tạo 1 Transaction rỗng "
            "(payment_status='PENDING') để thỏa FK bắt buộc Debt.transaction_id theo erd.md."
        ),
    )
    note: Optional[str] = Field(None, description="Ghi chú công nợ")
    input_method: Optional[str] = Field("MANUAL", description="Phương thức nhập theo ERD: 'VOICE' | 'MANUAL'")


class GhiNoNhaCungCapOutput(BaseModel):
    debt_id: int
    status: str          # 'UNPAID' | 'PARTIAL' | 'PAID' — theo enum Debt.status trong erd.md
    remaining_debt: float
    transaction_id: Optional[int] = None


class ThuNoNhaCungCapInput(BaseModel):
    account_id: int = Field(..., description="Tài khoản nguồn trích tiền trả, cột Account.account_id")
    amount: float = Field(..., gt=0, description="Số tiền trả cho nhà cung cấp")
    debt_id: Optional[int] = Field(None, description="Chỉ truyền khi biết rõ khoản nợ cụ thể cần trả")
    supplier_id: Optional[int] = Field(None, description="Chỉ truyền khi trả theo tổng tiền, để hệ thống tự phân bổ FIFO")
    note: Optional[str] = Field(None, description="Ghi chú phiếu chi trả nợ")
    input_method: Optional[str] = Field("MANUAL", description="Phương thức nhập theo ERD: 'VOICE' | 'MANUAL'")

    def model_post_init(self, __context) -> None:
        if not self.debt_id and not self.supplier_id:
            raise ValueError("Phải có debt_id hoặc supplier_id")
        if self.debt_id and self.supplier_id:
            raise ValueError("Chỉ được truyền MỘT trong hai: debt_id hoặc supplier_id, không truyền cả hai")


class ThuNoNhaCungCapOutput(BaseModel):
    # Có mặt ở cả 2 chế độ
    amount_paid: float
    payment_id: Optional[int] = None
    # Chế độ đích danh (debt_id) — có giá trị, còn lại None
    debt_id: Optional[int] = None
    remaining_debt: Optional[float] = None
    debt_status: Optional[str] = None
    # Chế độ FIFO (supplier_id) — có giá trị, còn lại None
    supplier_id: Optional[int] = None
    total_remaining_before: Optional[float] = None
    total_remaining_after: Optional[float] = None
    debts: Optional[List[DebtAllocationItem]] = None

