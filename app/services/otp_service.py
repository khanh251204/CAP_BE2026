import os
import hmac
import hashlib
import secrets

from datetime import datetime, timedelta

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

# LOAD ENV
load_dotenv()


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
        "JWT_SECRET_KEY chưa được cấu hình trong .env"
    )

# GENERATE OTP
def generate_otp() -> str:
    """
    Sinh OTP đúng 6 chữ số.

    Ví dụ:
    004821
    582039
    """

    return f"{secrets.randbelow(1_000_000):06d}"

# HASH OTP
def hash_otp(
    email: str,
    purpose: str,
    otp_code: str
) -> str:
    """
    Hash OTP bằng HMAC-SHA256.

    Database chỉ lưu otp_hash,
    không lưu OTP plaintext.
    """

    normalized_email = (
        email
        .strip()
        .lower()
    )

    message = (
        f"{normalized_email}:{purpose}:{otp_code}"
    ).encode("utf-8")

    return hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()

# VERIFY HASH
def verify_otp_hash(
    email: str,
    purpose: str,
    otp_code: str,
    stored_hash: str
) -> bool:
    """
    So sánh OTP người dùng nhập với otp_hash trong DB.
    """

    current_hash = hash_otp(
        email=email,
        purpose=purpose,
        otp_code=otp_code
    )

    return hmac.compare_digest(
        current_hash,
        stored_hash
    )

# CHECK COOLDOWN
def check_resend_cooldown(
    db: Session,
    *,
    email: str,
    purpose: str
):
    """
    Chặn gửi OTP liên tục.

    Ví dụ:
    OTP_RESEND_COOLDOWN_SECONDS = 60

    User phải chờ đủ 60 giây mới gửi lại.
    """

    normalized_email = (
        email
        .strip()
        .lower()
    )

    latest_otp = get_latest_otp(
        db,
        email=normalized_email,
        purpose=purpose
    )

    if not latest_otp:
        return

    now = datetime.utcnow()

    seconds_passed = (
        now - latest_otp.created_at
    ).total_seconds()

    if (
        seconds_passed
        < OTP_RESEND_COOLDOWN_SECONDS
    ):
        remaining = max(
            1,
            int(
                OTP_RESEND_COOLDOWN_SECONDS
                - seconds_passed
            )
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": (
                    "Vui lòng chờ trước khi gửi lại OTP"
                ),
                "resendAfter": remaining
            }
        )

# CREATE OTP
def create_otp_code(
    db: Session,
    *,
    user_id: int | None,
    email: str,
    purpose: str
) -> str:
    """
    Tạo OTP mới.

    Flow:
    1. Chuẩn hóa email
    2. Check cooldown
    3. Invalidate OTP cũ
    4. Sinh OTP mới
    5. Hash OTP
    6. Lưu otp_hash vào DB
    7. Trả OTP plaintext để email_service gửi mail

    Lưu ý:
    Function này KHÔNG commit.
    Service cấp cao hơn sẽ commit.
    """

    normalized_email = (
        email
        .strip()
        .lower()
    )

    # VALIDATE PURPOSE
    allowed_purposes = {
        "verify_email",
        "forgot_password"
    }

    if purpose not in allowed_purposes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP purpose không hợp lệ"
        )

    # COOLDOWN
    check_resend_cooldown(
        db,
        email=normalized_email,
        purpose=purpose
    )

    # INVALIDATE OLD OTP
    invalidate_old_otps(
        db,
        email=normalized_email,
        purpose=purpose
    )

    # GENERATE OTP
    otp_code = generate_otp()

    otp_hash = hash_otp(
        email=normalized_email,
        purpose=purpose,
        otp_code=otp_code
    )

    expires_at = (
        datetime.utcnow()
        + timedelta(
            minutes=OTP_EXPIRE_MINUTES
        )
    )

    # SAVE DB
    create_otp(
        db,
        user_id=user_id,
        email=normalized_email,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=expires_at
    )

    # Trả OTP plaintext để gửi email
    return otp_code

# VERIFY OTP
def verify_otp_code(
    db: Session,
    *,
    email: str,
    code: str,
    purpose: str
):
    """
    Xác thực OTP.

    Nếu đúng:
    - đánh dấu is_used = True
    - trả OTP record

    Nếu sai/hết hạn:
    - HTTPException
    """

    normalized_email = (
        email
        .strip()
        .lower()
    )

    # VALIDATE CODE
    if (
        len(code) != 6
        or not code.isdigit()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP phải gồm đúng 6 chữ số"
        )

    allowed_purposes = {
        "verify_email",
        "forgot_password"
    }

    if purpose not in allowed_purposes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP purpose không hợp lệ"
        )

    now = datetime.utcnow()

    # FIND VALID OTP
    otp = get_latest_valid_otp(
        db,
        email=normalized_email,
        purpose=purpose,
        now=now
    )

    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Mã OTP không tồn tại, "
                "đã hết hạn hoặc đã được sử dụng"
            )
        )

    # VERIFY HASH
    is_valid = verify_otp_hash(
        email=normalized_email,
        purpose=purpose,
        otp_code=code,
        stored_hash=otp.otp_hash
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không chính xác"
        )

    # MARK USED
    mark_otp_used(
        db,
        otp
    )

    return otp