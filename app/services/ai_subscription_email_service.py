"""
Email xác nhận đăng ký gói AI & Scheduler tự động gửi email nhắc sắp hết hạn (trước 3 ngày).
"""
import asyncio
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.configs.database import get_db_session
from app.models.user_ai_feature_model import UserAIFeature
from app.models.user_model import User
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

EXPIRY_REMINDER_DAYS = int(os.getenv("AI_PLAN_REMINDER_DAYS", "3"))
REMINDER_INTERVAL_SECONDS = int(os.getenv("AI_PLAN_REMINDER_INTERVAL_SECONDS", "21600"))  # 6 giờ


def _fmt_dt(dt: Optional[datetime]) -> str:
    return dt.strftime("%d/%m/%Y %H:%M") if dt else "Không giới hạn"


def _fmt_vnd(amount: int) -> str:
    return "Miễn phí" if amount <= 0 else f"{amount:,} đ".replace(",", ".")


def send_subscription_confirmation_email(
    *,
    to_email: str,
    full_name: str,
    plan_name: str,
    price_vnd: int,
    intent_count: int,
    subscribed_at: Optional[datetime],
    expires_at: Optional[datetime],
    user_id: Optional[int] = None,
) -> bool:
    """Gửi email xác nhận đăng ký / kích hoạt gói AI (không ném lỗi ra luồng chính)."""
    if not to_email:
        return False
    from app.services.email_management_service import get_email_settings

    cfg = get_email_settings()
    if not cfg.get("send_on_ai_subscribe", True):
        return False

    start_str = _fmt_dt(subscribed_at)
    end_str = _fmt_dt(expires_at)
    price_str = _fmt_vnd(price_vnd)
    reminder_days = int(cfg.get("expiry_reminder_days", EXPIRY_REMINDER_DAYS))
    note_text = cfg.get("confirm_body_note") or "Cảm ơn bạn đã đồng hành cùng VoiceCashBook!"
    subj_tpl = cfg.get("confirm_subject_template") or "[VoiceCashBook] Xác nhận kích hoạt {plan_name}"
    try:
        subject = subj_tpl.format(plan_name=plan_name, expires_at=end_str)
    except Exception:
        subject = f"[VoiceCashBook] Xác nhận kích hoạt {plan_name}"
    text = (
        f"Xin chào {full_name or 'Quý khách'},\n\n"
        f"Tài khoản của bạn đã được kích hoạt gói dịch vụ: {plan_name} ({price_str}/tháng).\n"
        f"- Số nghiệp vụ AI mở khóa: {intent_count} nghiệp vụ\n"
        f"- Ngày đăng ký: {start_str}\n"
        f"- Ngày hết hạn: {end_str}\n\n"
        f"{note_text}"
    )
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; color: #0f172a; line-height: 1.6;">
      <div style="background: #15803d; color: #ffffff; padding: 18px 22px; border-radius: 12px 12px 0 0;">
        <h2 style="margin: 0; font-size: 18px;">VoiceCashBook — Xác nhận đăng ký gói AI</h2>
      </div>
      <div style="border: 1px solid #e2e8f0; border-top: none; padding: 20px 22px; border-radius: 0 0 12px 12px;">
        <p>Xin chào <strong>{full_name or 'Quý khách'}</strong>,</p>
        <p>Gói dịch vụ AI của bạn đã được kích hoạt thành công với thông tin sau:</p>
        <table style="width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 14px;">
          <tr><td style="padding: 8px 0; color: #64748b;">Gói dịch vụ</td><td style="padding: 8px 0; font-weight: 700; text-align: right;">{plan_name}</td></tr>
          <tr><td style="padding: 8px 0; color: #64748b;">Cước phí</td><td style="padding: 8px 0; font-weight: 700; color: #15803d; text-align: right;">{price_str} / tháng</td></tr>
          <tr><td style="padding: 8px 0; color: #64748b;">Nghiệp vụ AI</td><td style="padding: 8px 0; font-weight: 600; text-align: right;">{intent_count} nghiệp vụ</td></tr>
          <tr><td style="padding: 8px 0; color: #64748b;">Ngày đăng ký</td><td style="padding: 8px 0; text-align: right;">{start_str}</td></tr>
          <tr><td style="padding: 8px 0; color: #64748b;">Ngày hết hạn</td><td style="padding: 8px 0; font-weight: 700; text-align: right;">{end_str}</td></tr>
        </table>
        <p style="font-size: 13px; color: #475569;">Hệ thống sẽ gửi email nhắc nhở trước khi gói hết hạn {reminder_days} ngày để bạn chủ động gia hạn.</p>
        <p style="font-size: 13px; color: #334155;">{note_text}</p>
      </div>
    </div>
    """
    try:
        send_email(
            to_email=to_email,
            subject=subject,
            text_content=text,
            html_content=html,
            email_type="AI_SUBSCRIPTION",
            user_id=user_id,
        )
        return True
    except Exception as exc:
        logger.warning("[AiPlanEmail] Không gửi được email xác nhận gói tới %s: %s", to_email, exc)
        return False


def send_subscription_confirmation_async(**kwargs: Any) -> None:
    """Chạy gửi email xác nhận ở luồng nền để không làm chậm API đăng ký."""
    t = threading.Thread(target=send_subscription_confirmation_email, kwargs=kwargs, daemon=True)
    t.start()


def send_subscription_expiring_email(
    *,
    to_email: str,
    full_name: str,
    plan_name: str,
    expires_at: datetime,
    days_remaining: int,
    user_id: Optional[int] = None,
) -> bool:
    if not to_email:
        return False
    from app.services.email_management_service import get_email_settings

    cfg = get_email_settings()
    end_str = _fmt_dt(expires_at)
    day_text = "hôm nay" if days_remaining <= 0 else f"sau {days_remaining} ngày"
    note_text = cfg.get("reminder_body_note") or (
        "Hãy mở ứng dụng VoiceCashBook → Gói dịch vụ AI để gia hạn kịp thời và tiếp tục sử dụng trợ lý giọng nói không gián đoạn."
    )
    subj_tpl = cfg.get("reminder_subject_template") or "[VoiceCashBook] Gói {plan_name} của bạn sắp hết hạn ({expires_at})"
    try:
        subject = subj_tpl.format(plan_name=plan_name, expires_at=end_str)
    except Exception:
        subject = f"[VoiceCashBook] Gói {plan_name} của bạn sắp hết hạn ({end_str})"
    text = (
        f"Xin chào {full_name or 'Quý khách'},\n\n"
        f"Gói dịch vụ AI '{plan_name}' của bạn sẽ hết hạn {day_text} (vào lúc {end_str}).\n"
        f"{note_text}\n\n"
        "Trân trọng,\nĐội ngũ VoiceCashBook"
    )
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; color: #0f172a; line-height: 1.6;">
      <div style="background: #d97706; color: #ffffff; padding: 18px 22px; border-radius: 12px 12px 0 0;">
        <h2 style="margin: 0; font-size: 18px;">VoiceCashBook — Nhắc gia hạn gói AI</h2>
      </div>
      <div style="border: 1px solid #e2e8f0; border-top: none; padding: 20px 22px; border-radius: 0 0 12px 12px;">
        <p>Xin chào <strong>{full_name or 'Quý khách'}</strong>,</p>
        <p>Gói dịch vụ <strong>{plan_name}</strong> của bạn sẽ hết hạn <strong>{day_text}</strong> (lúc <strong>{end_str}</strong>).</p>
        <p>{note_text}</p>
      </div>
    </div>
    """
    try:
        send_email(
            to_email=to_email,
            subject=subject,
            text_content=text,
            html_content=html,
            email_type="AI_EXPIRY_REMINDER",
            user_id=user_id,
        )
        return True
    except Exception as exc:
        logger.warning("[AiPlanEmail] Không gửi được email nhắc hết hạn tới %s: %s", to_email, exc)
        return False


def run_expiry_reminders(db: Optional[Session] = None, reminder_days: int = EXPIRY_REMINDER_DAYS) -> Dict[str, Any]:
    """
    Quét các tài khoản có gói AI sắp hết hạn trong vòng `reminder_days` ngày tới và chưa được nhắc
    (`expiry_reminded_at IS NULL`), gửi email nhắc và đánh dấu đã gửi.
    """
    from app.services.ai_feature_service import get_plans

    own_session = db is None
    sess = db or get_db_session()
    sent_user_ids: List[int] = []
    failed_user_ids: List[int] = []
    try:
        now = datetime.now()
        cutoff = now + timedelta(days=max(1, reminder_days))
        plans_map = get_plans(sess)

        rows = (
            sess.query(UserAIFeature, User)
            .join(User, User.user_id == UserAIFeature.user_id)
            .filter(
                UserAIFeature.expires_at.isnot(None),
                UserAIFeature.expires_at > now,
                UserAIFeature.expires_at <= cutoff,
                UserAIFeature.expiry_reminded_at.is_(None),
            )
            .all()
        )

        for feat, user in rows:
            plan_info = plans_map.get(feat.plan_code) if feat.plan_code else None
            plan_name = plan_info["name"] if plan_info else (feat.plan_code or "Gói AI")
            delta_days = max(0, int((feat.expires_at - now).total_seconds() // 86400))
            ok = send_subscription_expiring_email(
                to_email=user.email,
                full_name=user.full_name,
                plan_name=plan_name,
                expires_at=feat.expires_at,
                days_remaining=delta_days,
                user_id=user.user_id,
            )
            if ok:
                feat.expiry_reminded_at = now
                sent_user_ids.append(user.user_id)
            else:
                failed_user_ids.append(user.user_id)

        if sent_user_ids:
            sess.commit()

        return {
            "checked_count": len(rows),
            "sent_count": len(sent_user_ids),
            "failed_count": len(failed_user_ids),
            "sent_user_ids": sent_user_ids,
        }
    finally:
        if own_session:
            sess.close()


def send_subscription_renewal_email(
    *,
    to_email: str,
    full_name: str,
    plan_name: str,
    expires_at: datetime,
    days_expired: int,
    user_id: Optional[int] = None,
) -> bool:
    """Gửi email mời gia hạn lại khi gói AI đến ngày hết hạn hoặc đã hết hạn N ngày."""
    if not to_email:
        return False
    from app.services.email_management_service import get_email_settings

    cfg = get_email_settings()
    end_str = _fmt_dt(expires_at)
    expired_text = "hôm nay" if days_expired <= 0 else f"cách đây {days_expired} ngày"
    note_text = cfg.get("renewal_body_note") or (
        "Gói dịch vụ AI của bạn đã hết hạn. Mở ứng dụng VoiceCashBook → Gói dịch vụ AI để gia hạn lại và tiếp tục ghi sổ bằng giọng nói."
    )
    subj_tpl = (
        cfg.get("renewal_subject_template")
        or "[VoiceCashBook] Gói {plan_name} đã hết hạn — Gia hạn ngay để tiếp tục dùng AI"
    )
    try:
        subject = subj_tpl.format(plan_name=plan_name, expires_at=end_str)
    except Exception:
        subject = f"[VoiceCashBook] Gói {plan_name} đã hết hạn — Gia hạn ngay"

    text = (
        f"Xin chào {full_name or 'Quý khách'},\n\n"
        f"Gói dịch vụ AI '{plan_name}' của bạn đã hết hạn {expired_text} (vào lúc {end_str}).\n"
        f"{note_text}\n\n"
        "Trân trọng,\nĐội ngũ VoiceCashBook"
    )
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; color: #0f172a; line-height: 1.6;">
      <div style="background: #dc2626; color: #ffffff; padding: 18px 22px; border-radius: 12px 12px 0 0;">
        <h2 style="margin: 0; font-size: 18px;">VoiceCashBook — Gia hạn lại gói AI</h2>
      </div>
      <div style="border: 1px solid #e2e8f0; border-top: none; padding: 20px 22px; border-radius: 0 0 12px 12px;">
        <p>Xin chào <strong>{full_name or 'Quý khách'}</strong>,</p>
        <p>Gói dịch vụ <strong>{plan_name}</strong> của bạn đã hết hạn <strong>{expired_text}</strong> (lúc <strong>{end_str}</strong>).</p>
        <p>{note_text}</p>
      </div>
    </div>
    """
    try:
        send_email(
            to_email=to_email,
            subject=subject,
            text_content=text,
            html_content=html,
            email_type="AI_RENEWAL_REMINDER",
            user_id=user_id,
        )
        return True
    except Exception as exc:
        logger.warning("[AiPlanEmail] Không gửi được email mời gia hạn tới %s: %s", to_email, exc)
        return False


def run_renewal_reminders(db: Optional[Session] = None, after_days: int = 0) -> Dict[str, Any]:
    """
    Quét các tài khoản đã hết hạn gói AI từ `after_days` ngày trở lên (`expires_at <= now - after_days`)
    và chưa gửi email mời gia hạn (`renewal_reminded_at IS NULL`), gửi email mời gia hạn lại.
    """
    from app.services.ai_feature_service import get_plans

    own_session = db is None
    sess = db or get_db_session()
    sent_user_ids: List[int] = []
    failed_user_ids: List[int] = []
    try:
        now = datetime.now()
        cutoff = now - timedelta(days=max(0, after_days))
        plans_map = get_plans(sess)

        rows = (
            sess.query(UserAIFeature, User)
            .join(User, User.user_id == UserAIFeature.user_id)
            .filter(
                UserAIFeature.expires_at.isnot(None),
                UserAIFeature.expires_at <= cutoff,
                UserAIFeature.renewal_reminded_at.is_(None),
                UserAIFeature.plan_code != "locked",
            )
            .all()
        )

        for feat, user in rows:
            plan_info = plans_map.get(feat.plan_code) if feat.plan_code else None
            plan_name = plan_info["name"] if plan_info else (feat.plan_code or "Gói AI")
            days_expired = max(0, int((now - feat.expires_at).total_seconds() // 86400))
            ok = send_subscription_renewal_email(
                to_email=user.email,
                full_name=user.full_name,
                plan_name=plan_name,
                expires_at=feat.expires_at,
                days_expired=days_expired,
                user_id=user.user_id,
            )
            if ok:
                feat.renewal_reminded_at = now
                sent_user_ids.append(user.user_id)
            else:
                failed_user_ids.append(user.user_id)

        if sent_user_ids:
            sess.commit()

        return {
            "checked_count": len(rows),
            "sent_count": len(sent_user_ids),
            "failed_count": len(failed_user_ids),
            "sent_user_ids": sent_user_ids,
        }
    finally:
        if own_session:
            sess.close()


def run_all_scheduled_reminders(db: Optional[Session] = None) -> Dict[str, Any]:
    """Chạy đầy đủ cả 2 mốc tự động theo cấu hình Admin: (1) Sắp hết hạn trước X ngày, (2) Đã hết hạn sau Y ngày để gia hạn lại."""
    from app.services.email_management_service import get_email_settings, update_email_settings

    own_session = db is None
    sess = db or get_db_session()
    try:
        cfg = get_email_settings(sess)
        expiry_res = {"checked_count": 0, "sent_count": 0, "failed_count": 0, "sent_user_ids": []}
        renewal_res = {"checked_count": 0, "sent_count": 0, "failed_count": 0, "sent_user_ids": []}

        if cfg.get("auto_expiry_reminder", True):
            days = int(cfg.get("expiry_reminder_days", EXPIRY_REMINDER_DAYS))
            expiry_res = run_expiry_reminders(db=sess, reminder_days=days)

        if cfg.get("renewal_reminder_enabled", True):
            after_days = int(cfg.get("renewal_reminder_after_days", 0))
            renewal_res = run_renewal_reminders(db=sess, after_days=after_days)

        try:
            update_email_settings(sess, {"last_auto_run_at": datetime.now().isoformat()}, admin_id=None)
        except Exception:
            pass

        return {
            "expiry": expiry_res,
            "renewal": renewal_res,
            "total_checked": expiry_res["checked_count"] + renewal_res["checked_count"],
            "total_sent": expiry_res["sent_count"] + renewal_res["sent_count"],
            "total_failed": expiry_res["failed_count"] + renewal_res["failed_count"],
        }
    finally:
        if own_session:
            sess.close()


class AiSubscriptionReminderScheduler:
    """Scheduler nền tự động quét và gửi email nhắc sắp hết hạn & mời gia hạn lại gói AI."""

    _task: Optional[asyncio.Task] = None
    _running: bool = False

    @classmethod
    def start(cls) -> None:
        if cls._running:
            return
        cls._running = True
        cls._task = asyncio.create_task(cls._loop())
        logger.info("[AiPlanReminder] Scheduler đã khởi động")

    @classmethod
    def stop(cls) -> None:
        cls._running = False
        if cls._task and not cls._task.done():
            cls._task.cancel()
        cls._task = None

    @classmethod
    async def _loop(cls) -> None:
        # Chờ 60s sau khi server khởi động rồi mới chạy lần đầu
        await asyncio.sleep(60)
        while cls._running:
            sleep_seconds = REMINDER_INTERVAL_SECONDS
            try:
                from app.services.email_management_service import get_email_settings
                cfg = get_email_settings()
                interval_hours = max(1, min(24, int(cfg.get("schedule_interval_hours", 6))))
                sleep_seconds = interval_hours * 3600

                res = await asyncio.to_thread(run_all_scheduled_reminders, None)
                if res["total_sent"] > 0:
                    logger.info(
                        "[AiPlanReminder] Đã gửi %d email tự động (sắp hết hạn: %d, mời gia hạn: %d)",
                        res["total_sent"],
                        res["expiry"]["sent_count"],
                        res["renewal"]["sent_count"],
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("[AiPlanReminder] Lỗi chu kỳ quét: %s", exc)
            await asyncio.sleep(sleep_seconds)
