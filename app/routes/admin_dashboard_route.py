"""
Admin Dashboard — Router

Endpoints:
  GET /admin/dashboard                    — Summary KPIs (Revenue, Expense, Profit, Purchase, Debt, Counts)
  GET /admin/dashboard/trends             — Biểu đồ tài chính theo mốc thời gian (revenue, expense, profit)
  GET /admin/dashboard/top-products        — Top sản phẩm bán chạy nhất
  GET /admin/dashboard/expense-categories — Cơ cấu chi phí theo danh mục

Authorization: JWT + Role ADMIN (reuse authorize_roles từ jwt.py)
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authorize_roles
from app.schemas.admin_dashboard_schema import (
    AdminDashboardSummaryResponse,
    AdminDashboardTrendItem,
    AdminDashboardTopProductItem,
    AdminDashboardExpenseCategoryItem,
)
from app.services.admin_dashboard_service import AdminDashboardService


router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Admin - Dashboard"],
    dependencies=[Depends(authorize_roles("ADMIN", "admin"))]
)


@router.get(
    "",
    response_model=AdminDashboardSummaryResponse,
    summary="Xem tổng quan chỉ số Dashboard (Admin)",
    description=(
        "Tính toán các chỉ số KPI tổng quan toàn hệ thống (hoặc lọc theo user_id) "
        "cho khoảng thời gian chỉ định (Doanh thu, Chi phí, Lợi nhuận, Mua hàng, Công nợ, Số giao dịch)."
    ),
)
def get_dashboard_summary(
    period_type: Optional[str] = Query(None, description="Loại kỳ: DAY, MONTH, QUARTER, YEAR, CUSTOM"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng cụ thể"),
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_summary(
        db=db,
        period_type=period_type,
        from_date=date_from,
        to_date=date_to,
        user_id=user_id,
    )


@router.get(
    "/trends",
    response_model=List[AdminDashboardTrendItem],
    summary="Xem xu hướng tài chính theo thời gian (Admin)",
    description="Thống kê doanh thu, chi phí, lợi nhuận và số lượng giao dịch theo từng ngày trong khoảng thời gian chỉ định.",
)
def get_dashboard_trends(
    period_type: Optional[str] = Query(None, description="Loại kỳ: DAY, MONTH, QUARTER, YEAR, CUSTOM"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng cụ thể"),
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_trends(
        db=db,
        period_type=period_type,
        from_date=date_from,
        to_date=date_to,
        user_id=user_id,
    )


@router.get(
    "/top-products",
    response_model=List[AdminDashboardTopProductItem],
    summary="Xem danh sách Top sản phẩm bán chạy (Admin)",
    description="Xếp hạng các sản phẩm bán chạy nhất theo doanh thu hoặc số lượng bán.",
)
def get_top_products(
    period_type: Optional[str] = Query(None, description="Loại kỳ: DAY, MONTH, QUARTER, YEAR, CUSTOM"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng cụ thể"),
    limit: int = Query(5, ge=1, le=50, description="Số lượng sản phẩm lấy ra"),
    sort_by: str = Query("revenue", description="Sắp xếp theo: revenue (doanh thu) hoặc quantity (số lượng)"),
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_top_products(
        db=db,
        period_type=period_type,
        from_date=date_from,
        to_date=date_to,
        user_id=user_id,
        limit=limit,
        sort_by=sort_by,
    )


@router.get(
    "/expense-categories",
    response_model=List[AdminDashboardExpenseCategoryItem],
    summary="Xem cơ cấu chi phí theo danh mục (Admin)",
    description="Tổng hợp các khoản chi phí hoạt động phân loại theo danh mục thu/chi.",
)
def get_expense_categories(
    period_type: Optional[str] = Query(None, description="Loại kỳ: DAY, MONTH, QUARTER, YEAR, CUSTOM"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng cụ thể"),
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_expense_categories(
        db=db,
        period_type=period_type,
        from_date=date_from,
        to_date=date_to,
        user_id=user_id,
    )
