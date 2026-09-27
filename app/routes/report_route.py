from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session  

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.services.report_service import ReportService
from app.routes.reports.report_ws_route import (
    ws_router,
    handle_dashboard_report_ws,
    ws_reports_endpoint,
    ws_dashboard_endpoint
)
from app.schemas.report_schema import (
    LiveReportResponse,
    SummaryReportResponse,
    SalesReportResponse,
    PurchaseReportResponse,
    ExpenseReportResponse,
    DebtReportResponse,
    InventoryReportResponse,
    TransactionReportResponse,
    TransactionDetailReportResponse
)

router = APIRouter(tags=["Reporting"])
router.include_router(ws_router)


def extract_period_params(
    period_type: Optional[str] = Query(None, description="DAY, MONTH, QUARTER, YEAR"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD (cho DAY)"),
    year: Optional[int] = Query(None, description="Năm (cho MONTH, QUARTER, YEAR)"),
    month: Optional[int] = Query(None, description="Tháng 1-12 (cho MONTH)"),
    quarter: Optional[int] = Query(None, description="Quý 1-4 (cho QUARTER)"),
    from_date: Optional[str] = Query(None, alias="from", description="Khoảng từ ngày YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="Khoảng đến ngày YYYY-MM-DD")
):
    return {
        "period_type": period_type,
        "date_val": date,
        "year": year,
        "month": month,
        "quarter": quarter,
        "from_date": from_date,
        "to_date": to_date
    }


@router.get("/reports/live", response_model=LiveReportResponse)
def get_live_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_live_report(db, user_id, params)


@router.get("/reports/summary", response_model=SummaryReportResponse)
def get_summary_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_summary_report(db, user_id, params)


@router.get("/reports/sales", response_model=SalesReportResponse)
def get_sales_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_sales_report(db, user_id, params)


@router.get("/reports/purchases", response_model=PurchaseReportResponse)
def get_purchase_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_purchase_report(db, user_id, params)


@router.get("/reports/expenses", response_model=ExpenseReportResponse)
def get_expense_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_expense_report(db, user_id, params)


@router.get("/reports/debts", response_model=DebtReportResponse)
def get_debt_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_debt_report(db, user_id, params)


@router.get("/reports/inventory", response_model=InventoryReportResponse)
def get_inventory_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_inventory_report(db, user_id, params)


@router.get("/reports/transactions", response_model=TransactionReportResponse)
def get_transactions_report(
    params: dict = Depends(extract_period_params),
    intent: Optional[str] = Query(None, description="Tên intent (vd: ban_hang, mua_hang, chi_tien)"),
    category_id: Optional[int] = Query(None, description="ID danh mục"),
    payment_status: Optional[str] = Query(None, description="PAID, PARTIAL, PENDING"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_transactions_report(
        db=db,
        user_id=user_id,
        period_params=params,
        intent_name=intent,
        category_id=category_id,
        payment_status=payment_status,
        page=page,
        page_size=page_size
    )


@router.get("/reports/transactions/{transaction_id}", response_model=TransactionDetailReportResponse)
def get_transaction_detail(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ReportService.get_transaction_detail(db, user_id, transaction_id)


__all__ = [
    "router",
    "extract_period_params",
    "handle_dashboard_report_ws",
    "ws_reports_endpoint",
    "ws_dashboard_endpoint"
]
