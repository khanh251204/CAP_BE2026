from app.services.reports.sales_purchase_report import SalesPurchaseReportMixin
from app.services.reports.expense_debt_report import ExpenseDebtReportMixin
from app.services.reports.live_summary_report import LiveSummaryReportMixin
from app.services.reports.transaction_report import TransactionReportMixin


class ReportService(
    SalesPurchaseReportMixin,
    ExpenseDebtReportMixin,
    LiveSummaryReportMixin,
    TransactionReportMixin
):
    """
    Reporting Engine Facade:
    - READ-ONLY: Tuyệt đối không thay đổi hay ghi dữ liệu vào database.
    - Pure SQL Aggregation: Sử dụng func.sum, func.count, group_by... thay vì load Python loops.
    - User Isolation: Tất cả truy vấn đều bắt buộc lọc theo user_id.
    """
    pass


__all__ = ["ReportService"]
