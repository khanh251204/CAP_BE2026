from datetime import datetime
from typing import Optional, List, Tuple, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func, case

from app.models.voice_record_model import VoiceRecord
from app.models.transaction_model import Transaction
from app.models.user_model import User
from app.models.intent_model import Intent
from app.utils.vn_search import vn_ilike


class AdminVoiceRepository:

    @staticmethod
    def _build_base_filters(
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        intent: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list:
        filters = []

        # 1. Search transcript, user name, email, phone, intent, voice_id (hỗ trợ tìm không dấu)
        if search and search.strip():
            raw_kw = search.strip()
            search_conds = [
                vn_ilike(VoiceRecord.transcript, raw_kw),
                vn_ilike(User.full_name, raw_kw),
                vn_ilike(User.email, raw_kw),
                vn_ilike(User.phone_number, raw_kw),
                vn_ilike(VoiceRecord.intent, raw_kw),
                vn_ilike(Intent.intent_name, raw_kw),
            ]
            if raw_kw.isdigit():
                vid = int(raw_kw)
                search_conds.append(VoiceRecord.voice_id == vid)
                search_conds.append(VoiceRecord.user_id == vid)
            filters.append(or_(*search_conds))

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

        return filters

    @classmethod
    def get_voice_records(
        cls,
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

        filters = cls._build_base_filters(
            search=search,
            user_id=user_id,
            intent=intent,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            from_date=from_date,
            to_date=to_date,
        )

        # 4. Filter status
        if status and status.strip():
            clean_status = status.strip().upper()
            if clean_status == "PROCESSING":
                filters.append(func.upper(VoiceRecord.status).in_(["PROCESSING", "PENDING", "REVIEW"]))
            elif clean_status == "FAILED":
                filters.append(func.upper(VoiceRecord.status).in_(["FAILED", "ERROR", "CANCELLED", "REJECTED"]))
            elif clean_status == "SUCCESS":
                filters.append(or_(func.upper(VoiceRecord.status) == "SUCCESS", VoiceRecord.status.is_(None)))
            else:
                filters.append(VoiceRecord.status.ilike(clean_status))

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

    @classmethod
    def get_voice_status_counts(
        cls,
        db: Session,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        intent: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Đếm số lượng bản ghi theo từng trạng thái (SUCCESS, PROCESSING, FAILED, REVIEW)
        trên toàn bộ dữ liệu khớp với bộ lọc hiện tại (không phụ thuộc phân trang hay bộ lọc status).
        """
        normalized_status = func.coalesce(func.upper(VoiceRecord.status), "SUCCESS")
        query = (
            db.query(
                func.count(VoiceRecord.voice_id).label("total"),
                func.coalesce(
                    func.sum(case((normalized_status == "SUCCESS", 1), else_=0)), 0
                ).label("success"),
                func.coalesce(
                    func.sum(case((normalized_status.in_(["PROCESSING", "PENDING", "REVIEW"]), 1), else_=0)), 0
                ).label("processing"),
                func.coalesce(
                    func.sum(case((normalized_status.in_(["FAILED", "ERROR", "CANCELLED", "REJECTED"]), 1), else_=0)), 0
                ).label("failed"),
                func.coalesce(
                    func.sum(case((normalized_status == "REVIEW", 1), else_=0)), 0
                ).label("review"),
            )
            .select_from(VoiceRecord)
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

        filters = cls._build_base_filters(
            search=search,
            user_id=user_id,
            intent=intent,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            from_date=from_date,
            to_date=to_date,
        )
        if filters:
            query = query.filter(and_(*filters))

        row = query.first()
        if not row:
            return {"total": 0, "success": 0, "processing": 0, "failed": 0, "review": 0}

        return {
            "total": int(row.total or 0),
            "success": int(row.success or 0),
            "processing": int(row.processing or 0),
            "failed": int(row.failed or 0),
            "review": int(row.review or 0),
        }

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
