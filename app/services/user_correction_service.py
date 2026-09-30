import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user_correction_model import UserCorrection

logger = logging.getLogger(__name__)


class UserCorrectionService:
    """
    Service quản lý UserCorrection (Human-in-the-Loop) trong MySQL.
    Đảm bảo tính bền vững (persistence) cho dữ liệu hiệu chỉnh của người dùng,
    đồng bộ cùng Data Lake và phục vụ nghiên cứu / evaluation.
    """

    @staticmethod
    def save_user_correction(
        db: Session,
        voice_record_id: Optional[int],
        transaction_id: Optional[int],
        user_id: Optional[int],
        ai_result: Dict[str, Any],
        corrected_result: Dict[str, Any],
        diff: Dict[str, Any],
        correction_type: str = "MANUAL_EDIT",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UserCorrection]:
        """
        Lưu một bản ghi UserCorrection vào database.
        An toàn, không làm đứt gãy luồng chính nếu có lỗi DB.
        """
        try:
            correction = UserCorrection(
                user_id=user_id,
                voice_record_id=voice_record_id,
                transaction_id=transaction_id,
                correction_type=correction_type,
                original_ai_result=ai_result,
                corrected_result=corrected_result,
                diff=diff,
                extra_metadata=extra_metadata,
                created_at=datetime.now()
            )
            db.add(correction)
            db.commit()
            db.refresh(correction)
            logger.info(f"Đã lưu UserCorrection id={correction.id} cho voice_record_id={voice_record_id}")
            return correction
        except Exception as e:
            db.rollback()
            logger.warning(f"Lỗi khi lưu UserCorrection: {e}")
            return None

    @staticmethod
    def get_by_voice_id(db: Session, voice_record_id: int) -> Optional[UserCorrection]:
        """Truy vấn bản ghi correction theo voice_record_id."""
        return (
            db.query(UserCorrection)
            .filter(UserCorrection.voice_record_id == voice_record_id)
            .order_by(UserCorrection.id.desc())
            .first()
        )

    @staticmethod
    def get_by_transaction_id(db: Session, transaction_id: int) -> Optional[UserCorrection]:
        """Truy vấn bản ghi correction theo transaction_id."""
        return (
            db.query(UserCorrection)
            .filter(UserCorrection.transaction_id == transaction_id)
            .order_by(UserCorrection.id.desc())
            .first()
        )

    @staticmethod
    def list_corrections(
        db: Session,
        page: int = 1,
        limit: int = 20,
        user_id: Optional[int] = None,
        correction_type: Optional[str] = None
    ) -> Tuple[List[UserCorrection], int]:
        """Truy vấn danh sách UserCorrection có phân trang và bộ lọc."""
        query = db.query(UserCorrection)
        if user_id is not None:
            query = query.filter(UserCorrection.user_id == user_id)
        if correction_type:
            query = query.filter(UserCorrection.correction_type == correction_type)

        total = query.count()
        items = (
            query.order_by(UserCorrection.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        return items, total

    @staticmethod
    def count_total(db: Session) -> int:
        """Đếm tổng số bản ghi UserCorrection trong hệ thống."""
        return db.query(func.count(UserCorrection.id)).scalar() or 0
