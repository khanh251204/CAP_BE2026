"""
Khóa tài khoản khi đăng nhập sai mật khẩu nhiều lần.

- Sai MAX_FAILED_LOGIN_ATTEMPTS lần liên tiếp -> khóa, gửi mã OTP (purpose=unlock_account) về email.
- Chỉ mở bằng mã OTP từ email (hoặc admin mở). Không tự mở theo thời gian.
- Tài khoản do admin khóa (failed_attempts = 0) KHÔNG mở được bằng email.
"""
import logging
import os
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user_model import User
from app.models.user_lock_history_model import UserLockHistory

logger = logging.getLogger(__name__)

MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "3"))

# Khóa đến khi xác minh email: không có hạn tự mở
AUTO_LOCK_UNTIL = datetime(9999, 12, 31, 23, 59, 59)

# Mã lỗi để app biết chuyển sang màn nhập OTP mở khóa
ACCOUNT_LOCKED_CODE = "ACCOUNT_LOCKED"
ACCOUNT_LOCKED_BY_ADMIN_CODE = "ACCOUNT_LOCKED_BY_ADMIN"

# Lịch sử khóa / mở khóa (bảng User_Lock_History)
LOCK, UNLOCK = "LOCK", "UNLOCK"
REASON_TOO_MANY_FAILED_LOGINS = "TOO_MANY_FAILED_LOGINS"
REASON_ADMIN_LOCK = "ADMIN_LOCK"
REASON_EMAIL_OTP_UNLOCK = "EMAIL_OTP_UNLOCK"
REASON_ADMIN_UNLOCK = "ADMIN_UNLOCK"


def client_info(request) -> dict:
    """IP + thiết bị của request (FastAPI Request) để ghi vào lịch sử khóa."""
    if request is None:
        return {}
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else None)
    return {"ip_address": ip, "user_agent": (request.headers.get("user-agent") or "")[:255] or None}


def record_lock_event(
    db: Session,
    user: User,
    action: str,
    reason_code: str,
    reason: str | None = None,
    actor_id: int | None = None,
    client: dict | None = None,
) -> UserLockHistory | None:
    """Ghi một dòng lịch sử khóa / mở khóa (dùng savepoint để không làm rollback thao tác khóa chính)."""
    entry = UserLockHistory(
        user_id=user.user_id,
        action=action,
        reason_code=reason_code,
        reason=reason,
        actor_id=actor_id,
        ip_address=(client or {}).get("ip_address"),
        user_agent=(client or {}).get("user_agent"),
        created_at=datetime.utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(entry)
            db.flush()
        return entry
    except Exception as exc:
        logger.warning(f"Ghi User_Lock_History thất bại lần 1 ({exc}), thử tạo bảng và ghi lại...")
        try:
            UserLockHistory.__table__.create(bind=db.get_bind(), checkfirst=True)
            with db.begin_nested():
                db.add(entry)
                db.flush()
            return entry
        except Exception as retry_exc:
            logger.error(f"Không thể ghi lịch sử khóa cho user {user.user_id}: {retry_exc}", exc_info=True)
            return None


def is_locked(user: User) -> bool:
    return bool(user.lock_until and user.lock_until > datetime.utcnow())


def is_locked_by_failed_logins(user: User) -> bool:
    """Khóa do sai mật khẩu (mở được bằng email), khác với admin khóa."""
    return is_locked(user) and (user.failed_attempts or 0) >= MAX_FAILED_LOGIN_ATTEMPTS


def locked_error(user: User, otp_sent: bool = False) -> HTTPException:
    if is_locked_by_failed_logins(user):
        message = (
            f"Tài khoản đã bị tạm khóa do nhập sai mật khẩu {MAX_FAILED_LOGIN_ATTEMPTS} lần. "
            + ("Mã xác minh đã được gửi đến email của bạn. " if otp_sent else "")
            + "Vui lòng nhập mã xác minh từ email để mở khóa và nhận mật khẩu mới."
        )
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ACCOUNT_LOCKED_CODE,
                "message": message,
                "email": user.email,
                "otpSent": otp_sent,
            },
        )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": ACCOUNT_LOCKED_BY_ADMIN_CODE,
            "message": "Tài khoản đã bị tạm khóa. Vui lòng liên hệ quản trị viên.",
        },
    )


def register_failed_login(db: Session, user: User, client: dict | None = None) -> bool:
    """
    Tăng số lần sai (cộng trực tiếp trong DB để 2 request đồng thời không đếm thiếu).
    Đủ số lần -> khóa. Trả về True nếu lần này vừa khóa tài khoản.
    """
    db.query(User).filter(User.user_id == user.user_id).update(
        {User.failed_attempts: func.coalesce(User.failed_attempts, 0) + 1},
        synchronize_session=False,
    )
    db.refresh(user)
    if (user.failed_attempts or 0) >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.lock_until = AUTO_LOCK_UNTIL
        db.flush()
        record_lock_event(
            db, user, LOCK, REASON_TOO_MANY_FAILED_LOGINS,
            reason=f"Nhập sai mật khẩu {user.failed_attempts} lần liên tiếp",
            client=client,
        )
        return True
    return False


def reset_failed_logins(user: User) -> None:
    user.failed_attempts = 0


def unlock_account(user: User) -> None:
    user.failed_attempts = 0
    user.lock_until = None


def send_unlock_otp(db: Session, user: User) -> bool:
    """Gửi mã mở khóa về email. Lỗi gửi (hết lượt gửi lại, lỗi SMTP) không làm hỏng việc khóa."""
    from app.services.otp_service import send_otp, UNLOCK_ACCOUNT

    try:
        send_otp(db, user=user, purpose=UNLOCK_ACCOUNT)
        return True
    except HTTPException as exc:
        # 429: vừa gửi mã gần đây, mã cũ vẫn dùng được
        logger.info(f"Không gửi lại mã mở khóa cho user {user.user_id}: {exc.detail}")
        return exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    except Exception as exc:
        logger.error(f"Gửi mã mở khóa cho user {user.user_id} thất bại: {exc}", exc_info=True)
        return False
