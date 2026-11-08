from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.debt_model import Debt


class DebtDeleteMixin:
    @staticmethod
    def delete_debt(debt_id: int, user_id: int, db: Session) -> dict:
        """
        Xoá mềm một khoản nợ (is_active = False). Lịch sử thanh toán và giao dịch gốc được giữ nguyên,
        khoản nợ chỉ biến mất khỏi danh sách và các số liệu công nợ.
        """
        debt = db.query(Debt).filter(Debt.debt_id == debt_id, Debt.user_id == user_id).first()
        if not debt:
            raise HTTPException(status_code=404, detail="Không tìm thấy khoản nợ")

        try:
            debt.is_active = False
            db.commit()
        except Exception:
            db.rollback()
            raise

        return {
            "debt_id": debt_id,
            "direction": debt.direction,
            "remaining_debt": Decimal(str(debt.remaining_debt or 0)),
            "message": "Đã xoá khoản nợ",
        }
