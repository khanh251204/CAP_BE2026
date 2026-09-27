from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func

from app.models.voice_record_model import VoiceRecord
from app.models.transaction_model import Transaction
from app.models.user_model import User
from app.models.intent_model import Intent


class AdminVoiceRepository:

    @staticmethod
    def get_voice_records(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        intent: Optional[str] = None,
        status: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Tuple[List[Tuple[VoiceRecord, Optional[User], Optional[Transaction], Optional[str]]], int]:
        """
        Lấy danh sách bản ghi voice processing bằng truy vấn database tối ưu với SQL JOIN và Pagination.
        Trả về: (records, total_count)
        """
        # Base query with outer joins
        query = (
            db.query(
                VoiceRecord,
                User,
                Transaction,
                Intent.intent_name
            )
            .outerjoin(Transaction, VoiceRecord.transaction_id == Transaction.transaction_id)
            .outerjoin(
                User,
                or_(
                    VoiceRecord.user_id == User.user_id,
                    and_(VoiceRecord.user_id.is_(None), Transaction.user_id == User.user_id)
                )
            )
            .outerjoin(Intent, Transaction.intent_id == Intent.intent_id)
        )

        filters = []

        # 1. Search transcript
        if search and search.strip():
            keyword = f"%{search.strip()}%"
            filters.append(VoiceRecord.transcript.ilike(keyword))

        # 2. Filter user_id
        if user_id is not None:
            filters.append(
                or_(
                    VoiceRecord.user_id == user_id,
                    Transaction.user_id == user_id
                )
            )

        # 3. Filter intent
        if intent and intent.strip():
            clean_intent = intent.strip()
            filters.append(
                or_(
                    VoiceRecord.intent.ilike(clean_intent),
                    Intent.intent_name.ilike(clean_intent)
                )
            )

        # 4. Filter status
        if status and status.strip():
            clean_status = status.strip()
            filters.append(VoiceRecord.status.ilike(clean_status))

        # 5. Confidence range
        if confidence_min is not None:
            filters.append(VoiceRecord.confidence >= confidence_min)
        if confidence_max is not None:
            filters.append(VoiceRecord.confidence <= confidence_max)

        # 6. Date range
        if from_date is not None:
            filters.append(VoiceRecord.created_at >= from_date)
        if to_date is not None:
            filters.append(VoiceRecord.created_at <= to_date)

        if filters:
            query = query.filter(and_(*filters))

        # Đếm tổng số bản ghi thỏa điều kiện lọc bằng DB query
        total_count = query.with_entities(func.count(VoiceRecord.voice_id)).scalar() or 0

        # Pagination & Ordering
        offset = (page - 1) * limit
        records = (
            query
            .order_by(VoiceRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return records, total_count

    @staticmethod
    def get_voice_record_by_id(
        db: Session,
        voice_id: int
    ) -> Optional[Tuple[VoiceRecord, Optional[User], Optional[Transaction], Optional[str]]]:
        """
        Lấy chi tiết một bản ghi voice processing theo ID.
        """
        result = (
            db.query(
                VoiceRecord,
                User,
                Transaction,
                Intent.intent_name
            )
            .outerjoin(Transaction, VoiceRecord.transaction_id == Transaction.transaction_id)
            .outerjoin(
                User,
                or_(
                    VoiceRecord.user_id == User.user_id,
                    and_(VoiceRecord.user_id.is_(None), Transaction.user_id == User.user_id)
                )
            )
            .outerjoin(Intent, Transaction.intent_id == Intent.intent_id)
            .filter(VoiceRecord.voice_id == voice_id)
            .first()
        )
        return result
