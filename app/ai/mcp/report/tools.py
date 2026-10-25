import json
import logging
from typing import Any, Dict

from app.configs.database import SessionLocal
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)


class ReportTools:

    @staticmethod
    def get_summary_report(
        user_id: int,
        payload: Dict[str, Any]
    ) -> str:
        """
        MCP tool (READ-ONLY):
        Báo cáo tổng hợp doanh thu, nhập hàng, chi phí, lợi nhuận, công nợ theo kỳ.
        payload.period_params: tham số cho PeriodService.resolve_period (mặc định hôm nay).
        """
        db = SessionLocal()
        try:
            report = ReportService.get_summary_report(
                db=db,
                user_id=user_id,
                period_params=payload.get("period_params") or {}
            )
            return json.dumps(
                {"status": "success", "success": True, "report": report},
                ensure_ascii=False,
                default=str
            )
        except Exception:
            logger.exception("[Report MCP] Lỗi lấy báo cáo")
            return json.dumps(
                {
                    "status": "error",
                    "success": False,
                    "message": "Có lỗi xảy ra khi lấy báo cáo."
                },
                ensure_ascii=False
            )
        finally:
            db.close()
