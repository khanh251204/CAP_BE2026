"""
Admin Dashboard — Service Layer

Thực hiện các truy vấn aggregation trực tiếp trên Database cho Admin Dashboard:
- System KPIs (người dùng, giao dịch, xử lý giọng nói)
- Voice AI Processing & Voice Processing Trend
- User & Transaction Activity & Activity Trend
- Dataset / Data Lake Summary
- Recent System Activity
- System Health Check
"""
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, text

from app.models.user_model import User
from app.models.transaction_model import Transaction
from app.models.voice_record_model import VoiceRecord
from app.services.period_service import PeriodService


class AdminDashboardService:

    @classmethod
    def _validate_date_range(cls, from_date: Optional[str], to_date: Optional[str]) -> None:
        if from_date and to_date:
            try:
                dt_from = datetime.fromisoformat(from_date.strip())
                dt_to = datetime.fromisoformat(to_date.strip())
                if dt_from > dt_to:
                    raise HTTPException(
                        status_code=422,
                        detail="Ngày bắt đầu (from) không được lớn hơn ngày kết thúc (to)"
                    )
            except ValueError:
                # Nếu format không chuẩn ISO, PeriodService sẽ xử lý parse
                pass

    @classmethod
    def get_dashboard(
        cls,
        db: Session,
        period_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        cls._validate_date_range(from_date, to_date)

        period = PeriodService.resolve_period(
            period_type=period_type,
            from_date=from_date,
            to_date=to_date
        )
        start_dt = period["start_datetime"]
        end_dt = period["end_datetime"]

        # ========================================
        # 1. SYSTEM KPIS (Toàn thời gian)
        # ========================================
        total_users = db.query(func.count(User.user_id)).scalar() or 0
        active_users = db.query(func.count(User.user_id)).filter(
            User.is_verified.is_(True),
            or_(User.lock_until.is_(None), User.lock_until <= func.now())
        ).scalar() or 0

        total_tx = db.query(func.count(Transaction.transaction_id)).scalar() or 0

        voice_all = db.query(
            func.count(VoiceRecord.voice_id).label("total"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status) == "SUCCESS", 1), else_=0)), 0).label("success"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status) == "FAILED", 1), else_=0)), 0).label("failed"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status).in_(["REVIEW", "PENDING", "PROCESSING"]), 1), else_=0)), 0).label("pending_review")
        ).first()

        system_kpis = {
            "total_users": int(total_users),
            "active_users": int(active_users),
            "total_transactions": int(total_tx),
            "total_voice_processing": int(voice_all.total or 0) if voice_all else 0,
            "successful_voice_processing": int(voice_all.success or 0) if voice_all else 0,
            "failed_voice_processing": int(voice_all.failed or 0) if voice_all else 0,
            "pending_review_voice_processing": int(voice_all.pending_review or 0) if voice_all else 0,
        }

        # ========================================
        # 2. VOICE AI PROCESSING (Theo kỳ lọc)
        # ========================================
        voice_p_query = db.query(
            func.count(VoiceRecord.voice_id).label("total"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status) == "SUCCESS", 1), else_=0)), 0).label("success"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status) == "FAILED", 1), else_=0)), 0).label("failed"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status).in_(["REVIEW", "PENDING", "PROCESSING"]), 1), else_=0)), 0).label("pending_review")
        ).filter(VoiceRecord.created_at >= start_dt, VoiceRecord.created_at <= end_dt)

        if user_id is not None:
            voice_p_query = voice_p_query.filter(VoiceRecord.user_id == user_id)

        voice_p_res = voice_p_query.first()
        voice_processing_summary = {
            "total": int(voice_p_res.total or 0) if voice_p_res else 0,
            "success": int(voice_p_res.success or 0) if voice_p_res else 0,
            "failed": int(voice_p_res.failed or 0) if voice_p_res else 0,
            "pending_review": int(voice_p_res.pending_review or 0) if voice_p_res else 0,
        }

        # Voice processing trend (Group by ngày)
        vr_date_col = func.date(VoiceRecord.created_at)
        vr_trend_query = db.query(
            vr_date_col.label("v_date"),
            func.count(VoiceRecord.voice_id).label("total"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status) == "SUCCESS", 1), else_=0)), 0).label("success"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status) == "FAILED", 1), else_=0)), 0).label("failed"),
            func.coalesce(func.sum(case((func.upper(VoiceRecord.status).in_(["REVIEW", "PENDING", "PROCESSING"]), 1), else_=0)), 0).label("pending_review")
        ).filter(VoiceRecord.created_at >= start_dt, VoiceRecord.created_at <= end_dt)

        if user_id is not None:
            vr_trend_query = vr_trend_query.filter(VoiceRecord.user_id == user_id)

        vr_trend_rows = vr_trend_query.group_by(vr_date_col).order_by(vr_date_col.asc()).all()

        voice_processing_trend = [
            {
                "date": str(row[0]),
                "total": int(row[1] or 0),
                "success": int(row[2] or 0),
                "failed": int(row[3] or 0),
                "pending_review": int(row[4] or 0),
            }
            for row in vr_trend_rows if row[0] is not None
        ]

        # ========================================
        # 3. USER & TRANSACTION ACTIVITY (Theo kỳ lọc)
        # ========================================
        u_period_q = db.query(func.count(User.user_id)).filter(
            User.created_at >= start_dt, User.created_at <= end_dt
        )
        if user_id is not None:
            u_period_q = u_period_q.filter(User.user_id == user_id)
        new_users = u_period_q.scalar() or 0

        tx_period_q = db.query(func.count(Transaction.transaction_id)).filter(
            Transaction.created_at >= start_dt, Transaction.created_at <= end_dt
        )
        if user_id is not None:
            tx_period_q = tx_period_q.filter(Transaction.user_id == user_id)
        period_tx = tx_period_q.scalar() or 0

        activity_summary = {
            "new_users": int(new_users),
            "transactions": int(period_tx),
            "voice_processing": int(voice_processing_summary["total"]),
        }

        # Activity trend: Group by ngày cho new_users, transactions, voice
        u_date_col = func.date(User.created_at)
        u_trend_q = db.query(u_date_col, func.count(User.user_id)).filter(
            User.created_at >= start_dt, User.created_at <= end_dt
        )
        if user_id is not None:
            u_trend_q = u_trend_q.filter(User.user_id == user_id)
        u_trend_map = dict(u_trend_q.group_by(u_date_col).all())

        tx_date_col = func.date(Transaction.created_at)
        tx_trend_q = db.query(tx_date_col, func.count(Transaction.transaction_id)).filter(
            Transaction.created_at >= start_dt, Transaction.created_at <= end_dt
        )
        if user_id is not None:
            tx_trend_q = tx_trend_q.filter(Transaction.user_id == user_id)
        tx_trend_map = dict(tx_trend_q.group_by(tx_date_col).all())

        vr_daily_map = {row[0]: int(row[1] or 0) for row in vr_trend_rows if row[0] is not None}

        all_trend_dates = sorted(set(u_trend_map.keys()) | set(tx_trend_map.keys()) | set(vr_daily_map.keys()))
        activity_trend = [
            {
                "date": str(d),
                "new_users": int(u_trend_map.get(d, 0)),
                "transactions": int(tx_trend_map.get(d, 0)),
                "voice_processing": int(vr_daily_map.get(d, 0)),
            }
            for d in all_trend_dates if d is not None
        ]

        # ========================================
        # 4. DATASET / DATA LAKE SUMMARY
        # ========================================
        total_vr = db.query(func.count(VoiceRecord.voice_id)).scalar() or 0
        ds_records = db.query(func.count(VoiceRecord.voice_id)).filter(
            VoiceRecord.transcript.isnot(None),
            func.upper(VoiceRecord.status) == "SUCCESS"
        ).scalar() or 0
        corrections = db.query(func.count(VoiceRecord.voice_id)).filter(
            VoiceRecord.transaction_id.isnot(None)
        ).scalar() or 0

        dataset_summary = {
            "voice_records": int(total_vr),
            "dataset_records": int(ds_records),
            "corrections": int(corrections),
            "evaluation_records": None,  # Hệ thống hiện chưa có bảng evaluation trong DB
        }

        # ========================================
        # 5. RECENT SYSTEM ACTIVITY
        # ========================================
        recent_records = (
            db.query(VoiceRecord)
            .order_by(VoiceRecord.created_at.desc(), VoiceRecord.voice_id.desc())
            .limit(10)
            .all()
        )
        recent_activity = [
            {
                "id": r.voice_id,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
                "module": "VOICE",
                "action": f"PROCESS_{r.intent.upper()}" if r.intent else "PROCESS",
                "status": r.status or "SUCCESS",
                "description": r.transcript[:100] if r.transcript else None,
            }
            for r in recent_records
        ]

        # ========================================
        # 6. SYSTEM HEALTH
        # ========================================
        db_status = "healthy"
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_status = "unhealthy"

        ai_status = "healthy"
        if not (os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")):
            ai_status = "degraded"

        system_health = {
            "api": "healthy",
            "database": db_status,
            "ai_service": ai_status,
        }

        return {
            "period": {
                "period_type": period["period_type"],
                "start": period["start_datetime"].isoformat(),
                "end": period["end_datetime"].isoformat(),
            },
            "system": system_kpis,
            "voice_processing": voice_processing_summary,
            "voice_processing_trend": voice_processing_trend,
            "activity": activity_summary,
            "activity_trend": activity_trend,
            "dataset": dataset_summary,
            "recent_activity": recent_activity,
            "system_health": system_health,
            "summary": {
                "user_count": int(total_users),
                "transaction_count": int(total_tx),
                "voice_processing_count": int(system_kpis["total_voice_processing"]),
            },
        }

    # ========================================
    # Backward Compatibility Methods
    # ========================================
    @classmethod
    def get_summary(cls, db: Session, period_type: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        return cls.get_dashboard(db=db, period_type=period_type, from_date=from_date, to_date=to_date, user_id=user_id)

    @classmethod
    def get_trends(cls, db: Session, period_type: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        dash = cls.get_dashboard(db=db, period_type=period_type, from_date=from_date, to_date=to_date, user_id=user_id)
        return dash.get("activity_trend", [])

    @classmethod
    def get_top_products(cls, db: Session, **kwargs) -> List[Dict[str, Any]]:
        # Admin Dashboard không quản lý Top Products kinh doanh
        return []

    @classmethod
    def get_expense_categories(cls, db: Session, **kwargs) -> List[Dict[str, Any]]:
        # Admin Dashboard không quản lý cơ cấu chi phí kinh doanh
        return []
