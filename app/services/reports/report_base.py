from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.closing_period_model import ClosingPeriod
from app.models.user_model import User


class ReportBase:
    @classmethod
    def _check_period_closed(
        cls,
        db: Session,
        user_id: int,
        period_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Kiểm tra xem kỳ này đã được chốt (CLOSED) hay chưa.
        Chỉ lấy cờ is_closed và closing_id, KHÔNG lấy số liệu snapshot thay thế realtime.
        """
        p_type = period_info.get("period_type")
        p_start = period_info.get("period_start")
        p_end = period_info.get("period_end")

        if p_type in ["DAY", "MONTH", "QUARTER", "YEAR"]:
            closing = db.query(ClosingPeriod).filter(
                ClosingPeriod.user_id == user_id,
                ClosingPeriod.period_type == p_type,
                ClosingPeriod.period_start == p_start,
                ClosingPeriod.period_end == p_end,
                ClosingPeriod.status == "CLOSED"
            ).first()

            if closing:
                return {"is_closed": True, "closing_id": closing.closing_id}

        return {"is_closed": False, "closing_id": None}

    @classmethod
    def _get_user_business_type(cls, db: Session, user_id: int) -> str:
        """
        Lấy business_type của user. Mặc định trả về 'RESELLER' nếu chưa thiết lập.
        """
        user = db.query(User.business_type).filter(User.user_id == user_id).first()
        if user and user.business_type:
            return user.business_type.upper()
        return "RESELLER"
