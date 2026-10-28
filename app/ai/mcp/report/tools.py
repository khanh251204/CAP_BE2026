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

    # =========================================================
    # CHỐT SỔ (CLOSING PERIOD)
    # =========================================================

    @staticmethod
    def preview_closing(
        user_id: int,
        payload: Dict[str, Any]
    ) -> str:
        """
        MCP tool (READ-ONLY):
        Xem trước số liệu kỳ chốt sổ, không ghi DB.
        payload.period_params: tham số PeriodService.resolve_period (DAY / MONTH / QUARTER / YEAR).
        """
        from fastapi import HTTPException
        from app.services.closing_service import ClosingService

        db = SessionLocal()
        try:
            preview = ClosingService.preview_closing(db, user_id, payload.get("period_params") or {})
            return json.dumps(
                {"status": "success", "success": True, "preview": preview},
                ensure_ascii=False,
                default=str
            )
        except HTTPException as e:
            return json.dumps(
                {"status": "error", "success": False, "message": str(e.detail)},
                ensure_ascii=False
            )
        except Exception:
            logger.exception("[Report MCP] Lỗi xem trước chốt sổ")
            return json.dumps(
                {
                    "status": "error",
                    "success": False,
                    "message": "Có lỗi xảy ra khi xem trước chốt sổ."
                },
                ensure_ascii=False
            )
        finally:
            db.close()

    @staticmethod
    def close_period(
        user_id: int,
        payload: Dict[str, Any]
    ) -> str:
        """
        MCP tool:
        Chốt sổ kỳ (ClosingService.create_closing): ghi snapshot ClosingPeriod + ClosingTransaction
        trong một transaction, gửi email tổng kết. Kỳ đã chốt -> từ chối.
        """
        from fastapi import HTTPException
        from app.services.closing_service import ClosingService

        db = SessionLocal()
        try:
            closing = ClosingService.create_closing(
                db, user_id, payload.get("period_params") or {}, note=payload.get("note")
            )
            detail = ClosingService.get_closing_period_detail(db, user_id, closing.closing_id)
            return json.dumps(
                {
                    "status": "success",
                    "success": True,
                    "closing_id": closing.closing_id,
                    "closing": detail,
                },
                ensure_ascii=False,
                default=str
            )
        except HTTPException as e:
            db.rollback()
            return json.dumps(
                {"status": "error", "success": False, "message": str(e.detail)},
                ensure_ascii=False
            )
        except Exception:
            logger.exception("[Report MCP] Lỗi chốt sổ")
            db.rollback()
            return json.dumps(
                {
                    "status": "error",
                    "success": False,
                    "message": "Có lỗi xảy ra khi chốt sổ."
                },
                ensure_ascii=False
            )
        finally:
            db.close()
