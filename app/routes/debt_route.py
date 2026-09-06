from typing import Optional, List

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.debt_controller import DebtController
from app.schemas.debt_schema import (
    CreateCustomerDebtRequest,
    CreateCustomerDebtResponse,
    CollectCustomerDebtRequest,
    CollectCustomerDebtResponse,
    CustomerDebtItemResponse,
    CollectCustomerDebtByCustomerResponse,
)

debt_router = APIRouter(prefix="/debts", tags=["Debt — Customer"])


@debt_router.post(
    "/customer",
    response_model=CreateCustomerDebtResponse,
    summary="Tạo công nợ khách hàng (create_customer_debt / ghi_no_khach_hang)",
)
def create_customer_debt(
    request: CreateCustomerDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `create_customer_debt` (ghi_no_khach_hang)

    - Nhận `customer_id` + `total_debt`.
    - Nếu `transaction_id` không được truyền, server tự tạo Transaction rỗng loại
      *ghi nợ* với payment_status = PENDING (đáp ứng ràng buộc FK bắt buộc trong ERD).
    - Tạo bản ghi `Debt` với direction = RECEIVABLE, original_amount = total_debt, remaining_debt = total_debt, status = UNPAID.
    - Trả về `{ debt_id, status, total_debt, original_amount, remaining_debt }`.
    """
    return DebtController.create_customer_debt(
        db=db,
        user_id=user_id,
        customer_id=request.customer_id,
        total_debt=request.total_debt,
        transaction_id=request.transaction_id,
        note=request.note,
    )


@debt_router.get(
    "/customer",
    response_model=List[CustomerDebtItemResponse],
    summary="Lấy danh sách công nợ khách hàng (RECEIVABLE)",
)
def get_customer_debts(
    customer_id: Optional[int] = Query(None, description="Lọc theo ID khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PARTIAL, PAID"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên khách hàng"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Lấy danh sách toàn bộ công nợ của khách hàng nợ người dùng (direction = RECEIVABLE).
    Có thể lọc theo `customer_id`, trạng thái (`UNPAID`, `PARTIAL`, `PAID`) hoặc tìm kiếm tên.
    """
    return DebtController.get_customer_debts(
        user_id=user_id,
        db=db,
        customer_id=customer_id,
        status=status,
        search=search,
    )


@debt_router.post(
    "/customer/payments",
    response_model=CollectCustomerDebtResponse,
    summary="Thu tiền nợ khách hàng (nhận debt_id hoặc customer_id từ body)",
)
def collect_customer_debt_by_body(
    request: CollectCustomerDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Thu tiền nợ khách hàng linh hoạt:
    - Nếu truyền `debt_id`: Thu đích danh 1 khoản nợ.
    - Nếu truyền `customer_id`: Thu tổng theo khách hàng, tự động phân bổ FIFO.
    """
    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        debt_id=request.debt_id,
        customer_id=request.customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@debt_router.post(
    "/customer/{debt_id}/payments",
    response_model=CollectCustomerDebtResponse,
    summary="Thu tiền nợ khách hàng (collect_customer_debt / thu_no_khach_hang)",
)
def collect_customer_debt(
    debt_id: int = Path(..., description="ID công nợ cần thu"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `collect_customer_debt` (thu_no_khach_hang)

    Chạy trong **1 DB transaction**:
    1. Insert `Transaction` (intent = thu_no_khach_hang, total_amount = amount, payment_status = PAID)
    2. Insert `Debt_Payment` (liên kết debt_id, transaction_id, account_id, amount, payment_percentage)
    3. `UPDATE Account SET balance = balance + amount`
    4. Cập nhật `Debt.remaining_debt = remaining_debt - amount` và `Debt.status` (PARTIAL hoặc PAID)
    5. Cập nhật `payment_status` của Transaction gốc nếu có.

    **Validate**: `amount <= remaining_debt`, trả 400 nếu vượt.
    """
    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        debt_id=debt_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )

@debt_router.post(
    "/customer-account/{customer_id}/payments",
    response_model=CollectCustomerDebtByCustomerResponse,
    summary="Thu tiền nợ khách hàng - tự động phân bổ FIFO qua nhiều khoản nợ (collect_customer_debt)",
)
def collect_customer_debt_fifo(
    customer_id: int = Path(..., description="ID khách hàng cần thu nợ"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `collect_customer_debt` (thu_no_khach_hang) — chế độ FIFO theo khách hàng.
 
    Dùng khi khách đưa MỘT khoản tiền tổng, không chỉ rõ trả cho đơn nào
    (thường gặp với voice input, VD: "chị Lan trả 15 triệu"). Server tự
    tìm tất cả `Debt` đang mở (`status IN ('UNPAID','PARTIAL')`,
    `direction='RECEIVABLE'`) của khách hàng này, sắp theo `created_at`
    tăng dần (khoản nợ CŨ NHẤT trả trước), rồi trừ dần `amount` vào từng
    khoản cho tới khi hết tiền hoặc hết nợ.
 
    Chạy trong **1 DB transaction**:
    1. Lấy danh sách Debt đang mở của customer_id, sắp xếp FIFO theo created_at.
    2. Validate `amount <= tổng remaining_debt` của TẤT CẢ khoản đang mở —
       nếu vượt, trả 400 kèm tổng nợ hiện có, KHÔNG thu một phần rồi bỏ dở.
    3. Insert 1 `Transaction` duy nhất cho cả lượt thu (intent = thu_no_khach_hang,
       total_amount = amount, payment_status = PAID).
    4. Với mỗi Debt được phân bổ: insert 1 `Debt_Payment` tương ứng, cập nhật
       `remaining_debt` và `status` (PARTIAL hoặc PAID) của Debt đó, và cập
       nhật `payment_status` của Transaction gốc liên kết (nếu có).
    5. `UPDATE Account SET balance = balance + amount` (cộng đúng 1 lần).
 
    **Validate**: `amount <= tổng remaining_debt của tất cả khoản nợ đang mở
    của customer_id`, trả 400 nếu vượt (không so với từng khoản riêng lẻ).
    """
    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        customer_id=customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )

# ==========================================
# LẤY TẤT CẢ CÔNG NỢ
# GET /api/v1/debts/
# ==========================================
@debt_router.get("/")
def get_all_debts(
    name: Optional[str] = Query(default=None, description="Lọc theo 'customer', 'supplier', hoặc từ khóa tìm kiếm"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return DebtController.get_all_debts(
        user_id=user_id,
        db=db,
        name=name
    )