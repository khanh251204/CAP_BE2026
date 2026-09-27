from app.services.closing.closing_action_service import ClosingActionService
from app.services.closing.closing_query_service import ClosingQueryService
from app.services.closing.closing_setting_service import ClosingSettingService
from app.services.closing.closing_report_query_service import ClosingReportQueryService
from app.services.closing.closing_email_service import ClosingEmailService


class ClosingService(
    ClosingActionService,
    ClosingQueryService,
    ClosingSettingService,
    ClosingReportQueryService,
    ClosingEmailService
):
    """
    Closing Engine Facade:
    - Kế thừa toàn bộ nghiệp vụ action (preview, create, reopen).
    - Kế thừa toàn bộ nghiệp vụ query (get periods, detail, tx).
    - Kế thừa toàn bộ nghiệp vụ settings.
    - Kế thừa toàn bộ nghiệp vụ reports query & resend.
    - Kế thừa nghiệp vụ gửi email tổng kết chốt sổ.
    """
    pass


__all__ = ["ClosingService"]
