from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.otp_model import OTPCode
from app.configs.jwt import (
    create_reset_token,
    decode_reset_token,
    create_password_fingerprint,
    PASSWORD_RESET_EXPIRE_MINUTES
)
from app.configs.security import (
    get_password_hash,
    verify_password
)
from app.repositories.user_repository import (
    get_user_by_email,
    get_user_by_id,
    verify_user,
    update_user_password,
)
from app.repositories.refresh_token_repository import revoke_all_user_refresh_tokens
from app.schemas.auth_schema import (
    SendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)
from app.services.otp_service import (
    send_otp,
    verify_otp,
    OTP_EXPIRE_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS,
    VERIFY_EMAIL,
    FORGOT_PASSWORD,
    UNLOCK_ACCOUNT
)
from app.services.auth.account_lock_service import (
    is_locked_by_failed_logins,
    unlock_account,
    record_lock_event,
    UNLOCK,
    REASON_EMAIL_OTP_UNLOCK,
)
from app.services.auth.auth_registration_service import (
    normalize_email,
    validate_password_strength,
    user_to_dict
)
from app.services.auth.auth_login_service import create_session


def send_auth_otp(db: Session, data: SendOTPRequest):
    email = normalize_email(data.email)
    user = get_user_by_email(db, email)

    if data.purpose == VERIFY_EMAIL:
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
        if user.is_verified:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được xác thực")

    if data.purpose == FORGOT_PASSWORD:
        response = {
            "success": True,
            "message": "Nếu email tồn tại trong hệ thống, mã OTP sẽ được gửi đến email.",
            "otpExpiresIn": OTP_EXPIRE_MINUTES * 60,
            "resendCountdown": OTP_RESEND_COOLDOWN_SECONDS
        }
        if not user or not user.password_hash or not user.is_verified:
            return response

    if data.purpose == UNLOCK_ACCOUNT:
        unlock_response = {
            "success": True,
            "message": "Nếu tài khoản đang bị khóa, mã mở khóa sẽ được gửi đến email.",
            "otpExpiresIn": OTP_EXPIRE_MINUTES * 60,
            "resendCountdown": OTP_RESEND_COOLDOWN_SECONDS
        }
        if not user or not is_locked_by_failed_logins(user):
            return unlock_response

    try:
        otp_info = send_otp(db, user=user, purpose=data.purpose)
        db.commit()

        if data.purpose == FORGOT_PASSWORD:
            return {
                "success": True,
                "message": "Nếu email tồn tại trong hệ thống, mã OTP sẽ được gửi đến email.",
                **otp_info
            }

        if data.purpose == UNLOCK_ACCOUNT:
            return {**unlock_response, **otp_info}

        return {
            "success": True,
            "message": "Mã OTP đã được gửi",
            "email": user.email,
            **otp_info
        }
    except HTTPException as exc:
        db.rollback()
        if data.purpose == FORGOT_PASSWORD and exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            return {
                "success": True,
                "message": "Nếu email tồn tại trong hệ thống, mã OTP sẽ được gửi đến email.",
                "otpExpiresIn": OTP_EXPIRE_MINUTES * 60,
                "resendCountdown": OTP_RESEND_COOLDOWN_SECONDS
            }
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể gửi mã OTP"
        )


def verify_auth_otp(db: Session, data: VerifyOTPRequest, client: dict | None = None):
    email = normalize_email(data.email)
    user = get_user_by_email(db, email)

    if not user:
        if data.purpose in (FORGOT_PASSWORD, UNLOCK_ACCOUNT):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã OTP không hợp lệ hoặc đã hết hạn")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")

    if data.purpose == VERIFY_EMAIL and user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được xác thực")

    if data.purpose == FORGOT_PASSWORD and (not user.password_hash or not user.is_verified):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã OTP không hợp lệ hoặc đã hết hạn")

    # Admin khóa thì không mở bằng email được
    if data.purpose == UNLOCK_ACCOUNT and not is_locked_by_failed_logins(user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã OTP không hợp lệ hoặc đã hết hạn")

    try:
        verify_otp(db, user=user, code=data.code, purpose=data.purpose)

        if data.purpose == UNLOCK_ACCOUNT:
            # Mở khóa nhưng KHÔNG tự đăng nhập: người dùng vẫn phải nhập đúng mật khẩu
            unlock_account(user)
            record_lock_event(
                db, user, UNLOCK, REASON_EMAIL_OTP_UNLOCK,
                reason="Người dùng xác minh mã gửi về email để mở khóa",
                client=client,
            )
            db.commit()
            return {
                "success": True,
                "message": "Tài khoản đã được mở khóa. Vui lòng đăng nhập lại.",
                "nextAction": "login"
            }

        if data.purpose == VERIFY_EMAIL:
            verify_user(db, user)
            session = create_session(db, user)
            db.commit()
            db.refresh(user)

            return {
                "success": True,
                "message": "Xác thực email thành công",
                **session,
                "user": user_to_dict(user)
            }

        reset_token = create_reset_token(
            user_id=user.user_id,
            email=user.email,
            password_hash=user.password_hash
        )
        db.commit()

        return {
            "success": True,
            "message": "Xác thực OTP thành công",
            "resetToken": reset_token,
            "reset_token": reset_token,
            "forgotPasswordToken": reset_token,
            "expiresIn": PASSWORD_RESET_EXPIRE_MINUTES * 60,
            "nextAction": "forgot_password"
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xác thực OTP"
        )


def reset_password(db: Session, data: ResetPasswordRequest):
    validate_password_strength(data.newPassword)
    user = None

    if data.resetToken and data.resetToken.strip().lower() not in ("cookie", "undefined", "null", ""):
        try:
            payload = decode_reset_token(data.resetToken)
            user_id = int(payload["sub"])
            found_user = get_user_by_id(db, user_id)
            if found_user:
                token_email = normalize_email(payload.get("email", ""))
                if token_email == normalize_email(found_user.email):
                    fingerprint = create_password_fingerprint(found_user.password_hash)
                    if payload.get("passwordFingerprint") == fingerprint:
                        user = found_user
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Reset token không hợp lệ hoặc đã được sử dụng"
                        )
        except HTTPException:
            if not data.email:
                raise
            user = None

    if not user and data.email:
        clean_email = normalize_email(data.email)
        user = get_user_by_email(db, clean_email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản với email này")

        if data.otp:
            verify_otp(db, user=user, code=data.otp, purpose=FORGOT_PASSWORD)
        else:
            recent_otp = (
                db.query(OTPCode)
                .filter(
                    OTPCode.email == clean_email,
                    OTPCode.purpose == FORGOT_PASSWORD,
                    OTPCode.is_used == True,
                    OTPCode.created_at >= datetime.utcnow() - timedelta(minutes=15)
                )
                .order_by(OTPCode.otp_id.desc())
                .first()
            )
            if not recent_otp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vui lòng xác thực mã OTP trước khi đặt lại mật khẩu"
                )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thông tin xác thực không hợp lệ. Vui lòng thử lại từ bước gửi OTP."
        )

    try:
        update_user_password(db=db, user=user, password_hash=get_password_hash(data.newPassword))
        revoke_all_user_refresh_tokens(db=db, user_id=user.user_id, revoked_at=datetime.utcnow())
        db.commit()

        return {
            "success": True,
            "message": "Đặt lại mật khẩu thành công",
            "nextAction": "login"
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Không thể đặt lại mật khẩu")


forgot_password = reset_password


def change_user_password(db: Session, user_id: int, data: ChangePasswordRequest):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")

    if user.password_hash:
        if not data.oldPassword:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng nhập mật khẩu hiện tại")
        if not verify_password(data.oldPassword, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu hiện tại không chính xác")

    validate_password_strength(data.newPassword)

    if user.password_hash and verify_password(data.newPassword, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu mới không được trùng với mật khẩu hiện tại")

    try:
        update_user_password(db=db, user=user, password_hash=get_password_hash(data.newPassword))
        revoke_all_user_refresh_tokens(db=db, user_id=user.user_id, revoked_at=datetime.utcnow())
        db.commit()

        return {
            "success": True,
            "message": "Đổi mật khẩu thành công"
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Không thể đổi mật khẩu")
