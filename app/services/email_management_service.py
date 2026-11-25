"""
Service quản lý Email cho Admin:
- Nhật ký gửi email (Email_Log) + thống kê + gửi lại email lỗi
- Cấu hình tự động gửi email & lời nhắn mẫu (App_Setting key='email_settings')
- Kiểm tra trạng thái SMTP & gửi email test / gửi email thủ công theo nhóm
"""
import html as html_lib
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.models.app_setting_model import AppSetting
from app.models.email_log_model import EmailLog
from app.models.user_ai_feature_model import UserAIFeature
from app.models.user_model import User

logger = logging.getLogger(__name__)

EMAIL_SETTINGS_KEY = "email_settings"

DEFAULT_EMAIL_SETTINGS: Dict[str, Any] = {
    "send_on_ai_subscribe": True,
    "auto_expiry_reminder": True,
    "expiry_reminder_days": int(os.getenv("AI_PLAN_REMINDER_DAYS", "3")),
    "renewal_reminder_enabled": True,
    "renewal_reminder_after_days": 0,  # 0 = đúng ngày hết hạn, >0 = sau N ngày hết hạn
    "schedule_hour": 8,  # 0..23 giờ ưu tiên gửi trong ngày
    "schedule_interval_hours": 6,  # chu kỳ kiểm tra tự động (1..24 giờ)
    "last_auto_run_at": None,
    "confirm_subject_template": "[VoiceCashBook] Xác nhận kích hoạt {plan_name}",
    "confirm_body_note": "Cảm ơn bạn đã đồng hành cùng VoiceCashBook!",
    "reminder_subject_template": "[VoiceCashBook] Gói {plan_name} của bạn sắp hết hạn ({expires_at})",
    "reminder_body_note": "Hãy mở ứng dụng VoiceCashBook → Gói dịch vụ AI để gia hạn kịp thời và không gián đoạn ghi sổ bằng giọng nói.",
    "renewal_subject_template": "[VoiceCashBook] Gói {plan_name} đã hết hạn — Gia hạn ngay để tiếp tục dùng AI",
    "renewal_body_note": "Gói dịch vụ AI của bạn đã hết hạn. Mở ứng dụng VoiceCashBook → Gói dịch vụ AI để gia hạn lại và tiếp tục ghi sổ bằng giọng nói.",
}


def get_smtp_status() -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME") or ""
    password = os.getenv("SMTP_PASSWORD") or ""
    from_email = os.getenv("SMTP_FROM_EMAIL") or ""
    from_name = os.getenv("SMTP_FROM_NAME", "VoiceCashBook")

    missing = []
    if not host:
        missing.append("SMTP_HOST")
    if not username:
        missing.append("SMTP_USERNAME")
    if not password:
        missing.append("SMTP_PASSWORD")
    if not from_email:
        missing.append("SMTP_FROM_EMAIL")

    return {
        "configured": len(missing) == 0,
        "host": host,
        "port": port,
        "username": username,
        "from_email": from_email,
        "from_name": from_name,
        "missing_fields": missing,
    }


def record_email_log(
    *,
    to_email: str,
    subject: str,
    email_type: str = "OTHER",
    status: str = "SENT",
    error_message: Optional[str] = None,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
    user_id: Optional[int] = None,
    sent_by: Optional[int] = None,
    db: Optional[Session] = None,
) -> Optional[int]:
    """Ghi lịch sử email ở chế độ best-effort để không bao giờ làm hỏng luồng gửi mail chính."""
    own_session = db is None
    sess = None
    try:
        sess = db or get_db_session()
        row = EmailLog(
            to_email=(to_email or "")[:255],
            subject=(subject or "")[:255],
            email_type=(email_type or "OTHER")[:50],
            status=(status or "SENT")[:20],
            error_message=error_message,
            text_body=text_body,
            html_body=html_body,
            user_id=user_id,
            sent_by=sent_by,
        )
        sess.add(row)
        sess.commit()
        sess.refresh(row)
        return row.email_log_id
    except Exception as exc:
        logger.debug("[EmailLog] Bỏ qua ghi log email: %s", exc)
        if sess is not None and own_session:
            try:
                sess.rollback()
            except Exception:
                pass
        return None
    finally:
        if sess is not None and own_session:
            try:
                sess.close()
            except Exception:
                pass


def get_email_settings(db: Optional[Session] = None) -> Dict[str, Any]:
    own_session = db is None
    sess = None
    try:
        sess = db or get_db_session()
        row = sess.query(AppSetting).filter(AppSetting.setting_key == EMAIL_SETTINGS_KEY).first()
        merged = dict(DEFAULT_EMAIL_SETTINGS)
        if row and isinstance(row.value, dict):
            merged.update(row.value)
        return merged
    except Exception:
        return dict(DEFAULT_EMAIL_SETTINGS)
    finally:
        if sess is not None and own_session:
            try:
                sess.close()
            except Exception:
                pass


def update_email_settings(db: Session, updates: Dict[str, Any], admin_id: Optional[int] = None) -> Dict[str, Any]:
    current = get_email_settings(db)
    for key in DEFAULT_EMAIL_SETTINGS:
        if key in updates and updates[key] is not None:
            current[key] = updates[key]

    # Clamp numeric bounds
    current["expiry_reminder_days"] = max(1, min(30, int(current.get("expiry_reminder_days", 3))))
    current["renewal_reminder_after_days"] = max(0, min(60, int(current.get("renewal_reminder_after_days", 0))))
    current["schedule_hour"] = max(0, min(23, int(current.get("schedule_hour", 8))))
    current["schedule_interval_hours"] = max(1, min(24, int(current.get("schedule_interval_hours", 6))))

    row = db.query(AppSetting).filter(AppSetting.setting_key == EMAIL_SETTINGS_KEY).first()
    if row:
        row.value = current
        row.updated_at = datetime.now()
        row.updated_by = admin_id
    else:
        row = AppSetting(
            setting_key=EMAIL_SETTINGS_KEY,
            value=current,
            updated_at=datetime.now(),
            updated_by=admin_id,
        )
        db.add(row)
    db.commit()
    return current


def serialize_email_log(row: EmailLog, include_body: bool = False) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "email_log_id": row.email_log_id,
        "to_email": row.to_email,
        "subject": row.subject,
        "email_type": row.email_type,
        "status": row.status,
        "error_message": row.error_message,
        "user_id": row.user_id,
        "sent_by": row.sent_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if include_body:
        data["text_body"] = row.text_body
        data["html_body"] = row.html_body
    return data


def list_email_logs(
    db: Session,
    *,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    email_type: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    q = db.query(EmailLog)
    if search and search.strip():
        kw = f"%{search.strip()}%"
        q = q.filter(or_(EmailLog.to_email.ilike(kw), EmailLog.subject.ilike(kw)))
    if email_type and email_type != "ALL":
        q = q.filter(EmailLog.email_type == email_type)
    if status and status != "ALL":
        q = q.filter(EmailLog.status == status)

    total = q.count()
    items = (
        q.order_by(EmailLog.created_at.desc(), EmailLog.email_log_id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "items": [serialize_email_log(r, include_body=False) for r in items],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


def get_email_stats(db: Session) -> Dict[str, Any]:
    total = db.query(func.count(EmailLog.email_log_id)).scalar() or 0
    sent = db.query(func.count(EmailLog.email_log_id)).filter(EmailLog.status == "SENT").scalar() or 0
    failed = db.query(func.count(EmailLog.email_log_id)).filter(EmailLog.status == "FAILED").scalar() or 0

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sent = (
        db.query(func.count(EmailLog.email_log_id))
        .filter(EmailLog.status == "SENT", EmailLog.created_at >= today_start)
        .scalar()
        or 0
    )

    by_type_rows = (
        db.query(EmailLog.email_type, func.count(EmailLog.email_log_id))
        .group_by(EmailLog.email_type)
        .all()
    )
    by_type = {t: c for t, c in by_type_rows}
    success_rate = round((sent / total) * 100, 1) if total > 0 else 100.0

    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "today_sent": today_sent,
        "success_rate": success_rate,
        "by_type": by_type,
        "smtp": get_smtp_status(),
    }


def build_custom_html(subject: str, body_text: str) -> str:
    safe_subject = html_lib.escape(subject)
    paragraphs = "".join(
        f"<p style='margin: 0 0 12px;'>{html_lib.escape(line)}</p>" if line.strip() else "<br/>"
        for line in body_text.splitlines()
    )
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; color: #0f172a; line-height: 1.6;">
      <div style="background: #15803d; color: #ffffff; padding: 18px 22px; border-radius: 12px 12px 0 0;">
        <h2 style="margin: 0; font-size: 18px;">{safe_subject}</h2>
      </div>
      <div style="border: 1px solid #e2e8f0; border-top: none; padding: 20px 22px; border-radius: 0 0 12px 12px;">
        {paragraphs}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 18px 0;" />
        <p style="font-size: 12px; color: #64748b; margin: 0;">Email được gửi từ hệ thống quản trị VoiceCashBook.</p>
      </div>
    </div>
    """


def resolve_recipients(db: Session, mode: str, to_emails: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Trả về danh sách {email, user_id} theo chế độ gửi."""
    mode_upper = (mode or "SINGLE").upper()
    if mode_upper == "SINGLE":
        seen = set()
        out = []
        for raw in to_emails or []:
            addr = raw.strip().lower()
            if addr and "@" in addr and addr not in seen:
                seen.add(addr)
                out.append({"email": addr, "user_id": None})
        return out

    if mode_upper == "EXPIRING_AI":
        settings = get_email_settings(db)
        days = int(settings.get("expiry_reminder_days", 3))
        now = datetime.now()
        cutoff = now + timedelta(days=max(1, days))
        rows = (
            db.query(User.user_id, User.email)
            .join(UserAIFeature, UserAIFeature.user_id == User.user_id)
            .filter(
                User.email.isnot(None),
                User.email != "",
                UserAIFeature.expires_at.isnot(None),
                UserAIFeature.expires_at > now,
                UserAIFeature.expires_at <= cutoff,
            )
            .all()
        )
        return [{"email": r.email, "user_id": r.user_id} for r in rows if r.email]

    if mode_upper == "ALL_ACTIVE_USERS":
        now = datetime.now()
        rows = (
            db.query(User.user_id, User.email)
            .filter(
                User.email.isnot(None),
                User.email != "",
                or_(User.lock_until.is_(None), User.lock_until <= now),
            )
            .all()
        )
        return [{"email": r.email, "user_id": r.user_id} for r in rows if r.email]

    return []
