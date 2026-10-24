"""
Admin Transaction Management — Router

Endpoints:
  GET /admin/transactions          — Danh sách giao dịch (phân trang, search, filter, sort)
  GET /admin/transactions/{id}     — Chi tiết giao dịch

Authorization: JWT + quyền admin_* (require_admin_area + require_permission)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_permission, require_admin_area
from app.schemas.admin_transaction_schema import (
    AdminTransactionListResponse,
    AdminTransactionDetailResponse,
)
from app.services.admin_transaction_service import AdminTransactionService


router = APIRouter(
    prefix="/admin/transactions",
    tags=["Admin - Transaction Management"],
    dependencies=[Depends(require_admin_area)]
)


@router.get(
    "",
    response_model=AdminTransactionListResponse,
    summary="Xem danh sách giao dịch (Admin)",
    description=(
        "Truy vấn danh sách giao dịch toàn hệ thống với phân trang, "
        "tìm kiếm (theo transaction ID, nội dung, user), "
        "bộ lọc (intent, payment_status, input_method, user_id, ngày), "
        "và sắp xếp."
    ),
    dependencies=[Depends(require_permission("admin_transaction:read"))],
)
def list_transactions(
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi trên một trang"),
    search: Optional[str] = Query(
        None,
        description="Tìm theo transaction ID, nội dung (input_text/note), tên/email/cửa hàng User"
    ),
    user_id: Optional[int] = Query(None, description="Lọc theo user_id"),
    intent: Optional[str] = Query(
        None,
        description="Lọc theo tên intent (ban_hang, mua_hang, chi_tien...)"
    ),
    intent_type: Optional[str] = Query(
        None,
        description="Lọc theo loại intent (INCOME, EXPENSE, DEBT, TRANFER, REFUND, NONE)"
    ),
    payment_status: Optional[str] = Query(
        None,
        description="Lọc theo trạng thái thanh toán (PAID, PARTIAL, PENDING)"
    ),
    input_method: Optional[str] = Query(
        None,
        description="Lọc theo phương thức nhập (VOICE, MANUAL)"
    ),
    date_from: Optional[str] = Query(
        None, alias="from",
        description="Ngày bắt đầu (ISO 8601, ví dụ 2024-01-01)"
    ),
    date_to: Optional[str] = Query(
        None, alias="to",
        description="Ngày kết thúc (ISO 8601, ví dụ 2024-12-31)"
    ),
    sort_by: Optional[str] = Query(
        "created_at",
        description="Sắp xếp theo: created_at, transaction_date, total_amount, transaction_id"
    ),
    sort_order: Optional[str] = Query(
        "desc",
        description="Thứ tự sắp xếp: asc hoặc desc"
    ),
    db: Session = Depends(get_db),
):
    return AdminTransactionService.list_transactions(
        db=db,
        page=page,
        limit=limit,
        search=search,
        user_id=user_id,
        intent_name=intent,
        intent_type=intent_type,
        payment_status=payment_status,
        input_method=input_method,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by or "created_at",
        sort_order=sort_order or "desc",
    )


@router.get(
    "/{transaction_id}",
    response_model=AdminTransactionDetailResponse,
    summary="Xem chi tiết giao dịch (Admin)",
    description=(
        "Truy xuất chi tiết đầy đủ một giao dịch bao gồm: "
        "thông tin User, Intent, Category, Account, Customer/Supplier, "
        "và danh sách Transaction_Detail kèm Product."
    ),
    dependencies=[Depends(require_permission("admin_transaction:read"))],
)
def get_transaction_detail(
    transaction_id: int = Path(..., description="ID giao dịch"),
    db: Session = Depends(get_db),
):
    return AdminTransactionService.get_transaction_detail(
        db=db,
        transaction_id=transaction_id,
    )
