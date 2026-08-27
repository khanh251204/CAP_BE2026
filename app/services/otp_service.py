import os
import hmac
import hashlib
import secrets

from datetime import (
    datetime,
    timedelta
)

from dotenv import load_dotenv
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.otp_repository import (
    create_otp,
    get_latest_otp,
    get_latest_valid_otp,
    invalidate_old_otps,
    mark_otp_used
)

from app.services.email_service import (
    send_otp_email
)


load_dotenv()


# ============================================================
# OTP CONFIGURATION
# ============================================================

OTP_EXPIRE_MINUTES = int(
    os.getenv(
        "OTP_EXPIRE_MINUTES",
        "5"
    )
)

OTP_RESEND_COOLDOWN_SECONDS = int(
    os.getenv(
        "OTP_RESEND_COOLDOWN_SECONDS",
        "60"
    )
)

JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY"
)

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY chưa được cấu hình"
    )


VERIFY_EMAIL = "verify_email"
FORGOT_PASSWORD = "forgot_password"

ALLOWED_PURPOSES = {
    VERIFY_EMAIL,
    FORGOT_PASSWORD
}


# ============================================================
# GENERATE OTP
# ============================================================

def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


# ============================================================
# HASH OTP
# ============================================================

def _hash_otp(
    email: str,
    purpose: str,
    code: str
) -> str:

    message = (
        f"{email}:{purpose}:{code}"
    ).encode("utf-8")

    return hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


# ============================================================
# CHECK RESEND COOLDOWN
# ============================================================

def _check_cooldown(
    db: Session,
    email: str,
    purpose: str
):
    latest = get_latest_otp(
        db,
        email=email,
        purpose=purpose
    )

    if not latest:
        return

    passed = (
        datetime.utcnow()
        - latest.created_at
    ).total_seconds()

    if passed < OTP_RESEND_COOLDOWN_SECONDS:

        remaining = max(
            1,
            int(
                OTP_RESEND_COOLDOWN_SECONDS
                - passed
            )
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Vui lòng chờ trước khi gửi lại OTP",
                "resendAfter": remaining
            }
        )


# ============================================================
# SEND OTP
# ============================================================

def send_otp(
    db: Session,
    *,
    user,
    purpose: str
) -> dict:

    if purpose not in ALLOWED_PURPOSES:
        raise ValueError(
            "OTP purpose không hợp lệ"
        )

    email = user.email.strip().lower()

    _check_cooldown(
        db,
        email,
        purpose
    )

    # Vô hiệu hóa các OTP cũ
    invalidate_old_otps(
        db,
        email=email,
        purpose=purpose
    )

    # Tạo OTP mới
    code = _generate_otp()

    # Hash OTP trước khi lưu vào database
    otp_hash = _hash_otp(
        email,
        purpose,
        code
    )

    # Thời gian hết hạn OTP
    expires_at = (
        datetime.utcnow()
        + timedelta(
            minutes=OTP_EXPIRE_MINUTES
        )
    )

    create_otp(
        db,
        user_id=user.user_id,
        email=email,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=expires_at
    )

    # Gửi OTP qua email
    send_otp_email(
        to_email=email,
        otp_code=code,
        expire_minutes=OTP_EXPIRE_MINUTES,
        purpose=purpose
    )

    return {
        "otpExpiresIn": (
            OTP_EXPIRE_MINUTES * 60
        ),
        "resendCountdown": (
            OTP_RESEND_COOLDOWN_SECONDS
        )
    }


# ============================================================
# VERIFY OTP
# ============================================================

def verify_otp(
    db: Session,
    *,
    user,
    code: str,
    purpose: str
):

    if purpose not in ALLOWED_PURPOSES:
        raise ValueError(
            "OTP purpose không hợp lệ"
        )

    email = user.email.strip().lower()

    # Lấy OTP còn hiệu lực mới nhất
    otp = get_latest_valid_otp(
        db,
        email=email,
        purpose=purpose,
        now=datetime.utcnow()
    )

    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Mã OTP không hợp lệ "
                "hoặc đã hết hạn"
            )
        )

    # Kiểm tra OTP có thuộc đúng tài khoản hay không
    if (
        otp.user_id is not None
        and otp.user_id != user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không hợp lệ"
        )

    # Hash OTP người dùng nhập vào
    incoming_hash = _hash_otp(
        email,
        purpose,
        code
    )

    # So sánh hash an toàn
    if not hmac.compare_digest(
        incoming_hash,
        otp.otp_hash
    ):
        otp.attempts += 1
        if otp.attempts >= 5:
            otp.is_used = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP đã bị vô hiệu hóa do nhập sai quá 5 lần. Vui lòng gửi lại mã mới."
            )
        db.commit()
        remaining = 5 - otp.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã OTP không chính xác. Bạn còn {remaining} lần thử."
        )

    # Đánh dấu OTP đã được sử dụng
    mark_otp_used(
        db,
        otp
    )

    return otp