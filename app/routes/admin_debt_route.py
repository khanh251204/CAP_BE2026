"""
Admin Debt Management — Router

Endpoints:
  GET /admin/debts                  — Danh sách công nợ toàn hệ thống (phân trang, search, filter, sort)
  GET /admin/debts/summary          — Thống kê tổng quan KPI công nợ theo bộ lọc
  GET /admin/debts/{debt_id}        — Chi tiết khoản nợ kèm giao dịch gốc và lịch sử thanh toán
  GET /admin/debts/{debt_id}/payments — Danh sách các lần thanh toán của khoản nợ

Authorization: JWT + quyền admin_transaction:read (require_admin_area + require_permission)
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_admin_area, require_permission
from app.schemas.admin_debt_schema import (
    AdminDebtDetailResponse,
    AdminDebtListResponse,
    AdminDebtPaymentItem,
    AdminDebtSummaryResponse,
)
from app.services.admin_debt_service import AdminDebtService

router = APIRouter(
    prefix="/admin/debts",
    tags=["Admin - Debt Management"],
    dependencies=[Depends(require_admin_area)],
)


@router.get(
    "",
    response_model=AdminDebtListResponse,
    summary="Xem danh sách công nợ toàn hệ thống (Admin)",
    description=(
        "Truy vấn danh sách công nợ (Nợ phải thu khách hàng / Nợ phải trả nhà cung cấp) "
        "của toàn bộ cửa hàng với phân trang, tìm kiếm và bộ lọc."
    ),
    dependencies=[Depends(require_permission("admin_transaction:read"))],
)
def list_admin_debts(
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang"),
    search: Optional[str] = Query(
        None,
        description="Tìm theo mã nợ, tên/SĐT khách hàng hoặc NCC, tên/email/cửa hàng chủ shop, nội dung giao dịch",
    ),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng (chủ cửa hàng)"),
    direction: Optional[str] = Query(
        None,
        description="Chiều công nợ: RECEIVABLE (Nợ phải thu khách) hoặc PAYABLE (Nợ phải trả NCC)",
    ),
    status: Optional[str] = Query(
        None,
        description="Trạng thái công nợ: UNPAID, PARTIAL, PAID, hoặc OPEN (còn nợ: UNPAID + PARTIAL)",
    ),
    customer_id: Optional[int] = Query(None, description="Lọc theo ID khách hàng"),
    supplier_id: Optional[int] = Query(None, description="Lọc theo ID nhà cung cấp"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (ISO 8601, VD: 2026-01-01)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (ISO 8601, VD: 2026-12-31)"),
    sort_by: Optional[str] = Query(
        "created_at",
        description="Sắp xếp theo: created_at, updated_at, original_amount, remaining_debt, debt_id",
    ),
    sort_order: Optional[str] = Query("desc", description="Thứ tự sắp xếp: asc hoặc desc"),
    db: Session = Depends(get_db),
):
    return AdminDebtService.list_debts(
        db=db,
        page=page,
        limit=limit,
        search=search,
        user_id=user_id,
        direction=direction,
        status_filter=status,
        customer_id=customer_id,
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by or "created_at",
        sort_order=sort_order or "desc",
    )


@router.get(
    "/summary",
    response_model=AdminDebtSummaryResponse,
    summary="Thống kê KPI công nợ theo bộ lọc (Admin)",
    description=(
        "Tổng hợp số khoản nợ, tổng nợ gốc, đã thu/trả và còn phải thu/trả "
        "trên toàn bộ kết quả khớp bộ lọc."
    ),
    dependencies=[Depends(require_permission("admin_transaction:read"))],
)
def get_admin_debt_summary(
    search: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    supplier_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    return AdminDebtService.get_summary(
        db=db,
        search=search,
        user_id=user_id,
        direction=direction,
        status_filter=status,
        customer_id=customer_id,
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/{debt_id}",
    response_model=AdminDebtDetailResponse,
    summary="Xem chi tiết khoản công nợ (Admin)",
    description=(
        "Truy xuất chi tiết một khoản công nợ kèm thông tin chủ cửa hàng, "
        "khách hàng/nhà cung cấp, giao dịch gốc phát sinh nợ và lịch sử các lần thanh toán."
    ),
    dependencies=[Depends(require_permission("admin_transaction:read"))],
)
def get_admin_debt_detail(
    debt_id: int = Path(..., ge=1, description="ID khoản công nợ"),
    db: Session = Depends(get_db),
):
    return AdminDebtService.get_debt_detail(db=db, debt_id=debt_id)


@router.get(
    "/{debt_id}/payments",
    response_model=List[AdminDebtPaymentItem],
    summary="Lịch sử thanh toán của một khoản công nợ (Admin)",
    dependencies=[Depends(require_permission("admin_transaction:read"))],
)
def get_admin_debt_payments(
    debt_id: int = Path(..., ge=1, description="ID khoản công nợ"),
    db: Session = Depends(get_db),
):
    return AdminDebtService.get_debt_payments(db=db, debt_id=debt_id)
