from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Path, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.debt_controller import DebtController
from app.repositories.debt_repository import DebtRepository
from app.schemas.debt_schema import (
    CreateCustomerDebtRequest,
    CreateCustomerDebtResponse,
    CollectCustomerDebtRequest,
    CollectCustomerDebtResponse,
    CustomerDebtItemResponse,
    CollectCustomerDebtByCustomerResponse,
    CreateSupplierDebtRequest,
    CreateSupplierDebtResponse,
    PaySupplierDebtRequest,
    PaySupplierDebtResponse,
    SupplierDebtItemResponse,
    PaySupplierDebtBySupplierResponse,
    DebtSummaryResponse,
    PaginatedDebtListResponse,
    DebtDetailResponse,
    DebtPaymentHistoryItem,
    PayDebtRequest,
    PayDebtResponse,
)

debt_router = APIRouter(prefix="/debts", tags=["Debt Management"])


# ==========================================
# 1. DASHBOARD SUMMARY (Mục 6.1)
# Tuyệt đối phải đăng ký trước dynamic routes /{debt_id}
# ==========================================
@debt_router.get(
    "/summary",
    response_model=DebtSummaryResponse,
    summary="Thống kê tổng quan công nợ Dashboard (receivable & payable)",
)
def get_debt_summary(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Mục 6.1 Dashboard Summary**:
    - `receivable.total_remaining`: Tổng tiền khách nợ (Debt.direction = RECEIVABLE và status != PAID).
    - `receivable.count`: Số khoản nợ khách chưa trả hết.
    - `payable.total_remaining`: Tổng tiền nợ NCC (Debt.direction = PAYABLE và status != PAID).
    - `payable.count`: Số khoản nợ NCC chưa trả hết.
    - Thực hiện bằng SQL aggregation (`func.sum`, `func.count`), không load vòng lặp Python.
    """
    return DebtController.get_summary(user_id=user_id, db=db)


# ==========================================
# 2. CÔNG NỢ KHÁCH HÀNG (RECEIVABLE)
# ==========================================

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
    summary="Thu tiền nợ khách hàng linh hoạt qua body (Mục 7)",
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
    "/customer/{id}/payments",
    response_model=CollectCustomerDebtResponse,
    summary="Thu tiền nợ khách hàng (đích danh theo debt_id hoặc FIFO theo customer_id)",
)
def collect_customer_debt_by_id(
    id: int = Path(..., description="ID công nợ cần thu (nếu nợ cụ thể) hoặc ID khách hàng (nếu thu tổng FIFO)"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `collect_customer_debt` (thu_no_khach_hang)
    
    Hỗ trợ cả 2 mục 6.6 và 6.7:
    - Nếu `{id}` là `debt_id` thuộc user: Thu đích danh khoản nợ đó.
    - Nếu `{id}` là `customer_id` thuộc user: Thu tổng và tự động phân bổ FIFO.
    """
    debt_id = request.debt_id
    customer_id = request.customer_id

    if not debt_id and not customer_id:
        debt = DebtRepository.get_debt_by_id_and_user(debt_id=id, user_id=user_id, db=db, direction="RECEIVABLE")
        if debt:
            debt_id = id
        else:
            customer = DebtRepository.get_customer_by_id_and_user(customer_id=id, user_id=user_id, db=db)
            if customer:
                customer_id = id
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Không tìm thấy công nợ hoặc khách hàng với ID {id}"
                )

    return DebtController.collect_customer_debt(
        db=db,
        user_id=user_id,
        debt_id=debt_id,
        customer_id=customer_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@debt_router.post(
    "/customer-account/{customer_id}/payments",
    response_model=CollectCustomerDebtByCustomerResponse,
    summary="Thu tiền nợ khách hàng - tự động phân bổ FIFO qua nhiều khoản nợ (Compatibility alias)",
)
def collect_customer_debt_fifo(
    customer_id: int = Path(..., description="ID khách hàng cần thu nợ"),
    request: CollectCustomerDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `collect_customer_debt` (thu_no_khach_hang) — chế độ FIFO theo khách hàng.
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
# 3. CÔNG NỢ NHÀ CUNG CẤP (PAYABLE)
# ==========================================

@debt_router.post(
    "/supplier",
    response_model=CreateSupplierDebtResponse,
    summary="Tạo công nợ nhà cung cấp (create_supplier_debt / ghi_no_nha_cung_cap)",
)
def create_supplier_debt(
    request: CreateSupplierDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `create_supplier_debt` (ghi_no_nha_cung_cap)
    """
    return DebtController.create_supplier_debt(
        db=db,
        user_id=user_id,
        supplier_id=request.supplier_id,
        total_debt=request.total_debt,
        transaction_id=request.transaction_id,
        note=request.note,
    )


@debt_router.get(
    "/supplier",
    response_model=List[SupplierDebtItemResponse],
    summary="Lấy danh sách công nợ nhà cung cấp (PAYABLE)",
)
def get_supplier_debts(
    supplier_id: Optional[int] = Query(None, description="Lọc theo ID nhà cung cấp"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PARTIAL, PAID"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên nhà cung cấp"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.get_supplier_debts(
        user_id=user_id,
        db=db,
        supplier_id=supplier_id,
        status=status,
        search=search,
    )


@debt_router.post(
    "/supplier/payments",
    response_model=PaySupplierDebtResponse,
    summary="Trả tiền nợ nhà cung cấp linh hoạt qua body (Mục 7)",
)
def pay_supplier_debt_by_body(
    request: PaySupplierDebtRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.pay_supplier_debt(
        db=db,
        user_id=user_id,
        debt_id=request.debt_id,
        supplier_id=request.supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@debt_router.post(
    "/supplier/{id}/payments",
    response_model=PaySupplierDebtResponse,
    summary="Trả tiền nợ nhà cung cấp (đích danh theo debt_id hoặc FIFO theo supplier_id)",
)
def pay_supplier_debt_by_id(
    id: int = Path(..., description="ID công nợ cần trả (nếu nợ cụ thể) hoặc ID nhà cung cấp (nếu trả tổng FIFO)"),
    request: PaySupplierDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Intent**: `pay_supplier_debt` (thu_no_nha_cung_cap / tra_no_nha_cung_cap)
    
    Hỗ trợ cả 2 mục 6.9 và 6.10:
    - Nếu `{id}` là `debt_id` thuộc user: Trả đích danh khoản nợ đó.
    - Nếu `{id}` là `supplier_id` thuộc user: Trả tổng và tự động phân bổ FIFO.
    """
    debt_id = request.debt_id
    supplier_id = request.supplier_id

    if not debt_id and not supplier_id:
        debt = DebtRepository.get_debt_by_id_and_user(debt_id=id, user_id=user_id, db=db, direction="PAYABLE")
        if debt:
            debt_id = id
        else:
            supplier = DebtRepository.get_supplier_by_id_and_user(supplier_id=id, user_id=user_id, db=db)
            if supplier:
                supplier_id = id
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Không tìm thấy công nợ hoặc nhà cung cấp với ID {id}"
                )

    return DebtController.pay_supplier_debt(
        db=db,
        user_id=user_id,
        debt_id=debt_id,
        supplier_id=supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


@debt_router.post(
    "/supplier-account/{supplier_id}/payments",
    response_model=PaySupplierDebtBySupplierResponse,
    summary="Trả tiền nợ nhà cung cấp - tự động phân bổ FIFO qua nhiều khoản nợ (Compatibility alias)",
)
def pay_supplier_debt_fifo(
    supplier_id: int = Path(..., description="ID nhà cung cấp cần trả nợ"),
    request: PaySupplierDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtController.pay_supplier_debt(
        db=db,
        user_id=user_id,
        supplier_id=supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
    )


# ==========================================
# 4. THANH TOÁN THEO ĐÚNG KHOẢN NỢ (Mục 10 & 11)
# ==========================================
@debt_router.post(
    "/{debt_id}/payments",
    response_model=PayDebtResponse,
    summary="Thanh toán chính xác theo debt_id (Mục 10 & 11)",
)
def pay_debt_by_id(
    debt_id: int = Path(..., ge=1, description="ID công nợ cần thanh toán"),
    request: PayDebtRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    **Thanh toán đúng theo debt_id** (Mục 10 & 11 [AGENTS.md]):
    - Tự động nhận diện RECEIVABLE (khách trả nợ -> cộng ví) hoặc PAYABLE (trả NCC -> trừ ví).
    - Kiểm tra tính hợp lệ của tài khoản, số tiền thanh toán không vượt quá nợ còn lại.
    - PAYABLE: kiểm tra số dư ví phải >= số tiền trả (cấm số dư âm).
    - Cập nhật số dư Account, trạng thái Debt (UNPAID -> PARTIAL -> PAID), remaining_debt, lưu DebtPayment và Transaction thanh toán.
    - Transaction thực hiện atomic, rollback toàn bộ nếu có lỗi.
    """
    return DebtController.pay_debt_exact(
        debt_id=debt_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
        user_id=user_id,
        db=db,
    )


# ==========================================
# 5. LỊCH SỬ THANH TOÁN (Mục 6.4 & Mục 12)
# ==========================================
@debt_router.get(
    "/{debt_id}/payments",
    response_model=List[DebtPaymentHistoryItem],
    summary="Lịch sử thanh toán của một khoản nợ (Mục 6.4 & Mục 12)",
)
def get_debt_payments(
    debt_id: int = Path(..., ge=1, description="ID công nợ cần xem lịch sử thanh toán"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Trả danh sách `Debt_Payment` của khoản nợ, sắp xếp `payment_date DESC, created_at DESC`.
    Bảo mật kiểm tra ownership qua `Debt.user_id`.
    """
    return DebtController.get_payment_history(debt_id=debt_id, user_id=user_id, db=db)


# ==========================================
# 5. CHI TIẾT CÔNG NỢ (Mục 6.3)
# ==========================================
@debt_router.get(
    "/{debt_id}",
    response_model=DebtDetailResponse,
    summary="Chi tiết khoản công nợ kèm thông tin đối tác, giao dịch và thanh toán (Mục 6.3)",
)
def get_debt_detail(
    debt_id: int = Path(..., ge=1, description="ID công nợ cần xem chi tiết"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Trả về chi tiết khoản công nợ:
    - debt info (debt_id, direction, original_amount, remaining_debt, status)
    - customer hoặc supplier info
    - transaction info (intent_name, input_text, transaction_date) nếu có
    - payment history
    """
    return DebtController.get_debt_detail(debt_id=debt_id, user_id=user_id, db=db)


# ==========================================
# 6. LẤY TẤT CẢ CÔNG NỢ CÓ PHÂN TRANG (Mục 6.2)
# ==========================================
@debt_router.get(
    "",
    response_model=PaginatedDebtListResponse,
    summary="Lấy danh sách tất cả công nợ có phân trang và bộ lọc (Mục 6.2)",
)
@debt_router.get(
    "/",
    response_model=PaginatedDebtListResponse,
    include_in_schema=False,
)
def get_all_debts(
    direction: Optional[str] = Query(None, description="Lọc theo chiều nợ: RECEIVABLE, PAYABLE"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PARTIAL, PAID"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên khách hàng hoặc nhà cung cấp"),
    customer_id: Optional[int] = Query(None, description="Lọc theo ID khách hàng"),
    supplier_id: Optional[int] = Query(None, description="Lọc theo ID nhà cung cấp"),
    page: int = Query(1, ge=1, description="Số trang (mặc định 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang (mặc định 20, tối đa 100)"),
    name: Optional[str] = Query(None, description="Tương thích ngược: lọc tên đối tác hoặc direction"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    effective_search = search
    effective_direction = direction

    if name:
        if name.upper() in ["RECEIVABLE", "PAYABLE"]:
            effective_direction = name.upper()
        elif not effective_search and name.lower() not in ["customer", "supplier"]:
            effective_search = name

    return DebtController.get_debts_paginated(
        user_id=user_id,
        db=db,
        direction=effective_direction,
        status=status,
        search=effective_search,
        customer_id=customer_id,
        supplier_id=supplier_id,
        page=page,
        limit=limit,
    )