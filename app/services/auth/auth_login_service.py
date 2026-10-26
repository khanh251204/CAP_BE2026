import logging
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.configs.jwt import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.configs.roles import Roles
from app.configs.security import verify_password
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_google_id,
    link_google_account,
)
from app.schemas.auth_schema import LoginRequest, GoogleLoginRequest
from app.services.google_auth_service import verify_google_id_token
from app.services.refresh_token_service import (
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token_value,
    purge_expired_refresh_tokens
)
from app.services.auth.auth_registration_service import normalize_email, user_to_dict
from app.services.system_log_service import log_event
from app.services.auth.account_lock_service import (
    MAX_FAILED_LOGIN_ATTEMPTS,
    is_locked,
    locked_error,
    register_failed_login,
    reset_failed_logins,
    send_unlock_otp,
)

logger = logging.getLogger(__name__)


def record_user_login(user_id: int | str):
    try:
        from app.configs.firebase import db
        from firebase_admin import firestore
        db.collection("user_activity").document(str(user_id)).set({
            "userId": str(user_id),
            "lastLoginAt": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    except Exception as e:
        logger.warning(f"Failed to record user activity for {user_id}: {e}")


def create_session(db: Session, user) -> dict:
    access_token = create_access_token({
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "business_type": user.business_type
    })

    refresh_token = create_refresh_token(
        db=db,
        user_id=user.user_id,
        email=user.email,
        role=user.role
    )

    record_user_login(user.user_id)

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "bearer",
        "expiresIn": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


def create_access_session(user) -> dict:
    access_token = create_access_token({
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
        "business_type": user.business_type
    })

    return {
        "accessToken": access_token,
        "tokenType": "bearer",
        "expiresIn": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


def login_user(db: Session, data: LoginRequest, client: dict | None = None):
    email = normalize_email(data.email)
    user = get_user_by_email(db, email)

    # Kiểm tra khóa TRƯỚC mật khẩu: tài khoản đang khóa thì không cho dò mật khẩu tiếp
    if user and is_locked(user):
        log_event(
            level="WARNING",
            step="AUTH",
            message=f"Login blocked: account is locked for {email}",
            detail={"reason": "ACCOUNT_LOCKED", "email": email},
            user_id=user.user_id
        )
        raise locked_error(user)

    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        log_event(
            level="WARNING",
            step="AUTH",
            message=f"Login failed: invalid email or password for {email}",
            detail={"reason": "INVALID_CREDENTIALS", "email": email}
        )
        # Chỉ đếm với tài khoản có mật khẩu (tài khoản chỉ dùng Google không đăng nhập bằng mật khẩu)
        if user and user.password_hash:
            try:
                just_locked = register_failed_login(db, user, client=client)
                otp_sent = send_unlock_otp(db, user) if just_locked else False
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Không ghi được lần đăng nhập sai cho {email}: {e}", exc_info=True)
                just_locked, otp_sent = False, False
            if just_locked:
                log_event(
                    level="WARNING",
                    step="AUTH",
                    message=f"Account locked after {MAX_FAILED_LOGIN_ATTEMPTS} failed logins: {email}",
                    detail={"reason": "TOO_MANY_FAILED_LOGINS", "email": email, "otpSent": otp_sent},
                    user_id=user.user_id
                )
                raise locked_error(user, otp_sent=otp_sent)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác"
        )

    if not user.is_verified:
        log_event(
            level="WARNING",
            step="AUTH",
            message=f"Login blocked: unverified email for {email}",
            detail={"reason": "EMAIL_NOT_VERIFIED", "email": email},
            user_id=user.user_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được xác thực email"
        )

    # Đăng nhập đúng -> đếm lại từ đầu
    reset_failed_logins(user)

    try:
        session = create_session(db, user)
        db.commit()
        db.refresh(user)
        return {
            "success": True,
            **session,
            "user": user_to_dict(user)
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng nhập"
        )


DEFAULT_GOOGLE_BUSINESS_TYPE = "RESELLER"


def google_login(db: Session, data: GoogleLoginRequest):
    google_data = verify_google_id_token(data.idToken)
    google_id = google_data["googleId"]
    email = normalize_email(google_data["email"])

    try:
        user = get_user_by_google_id(db, google_id)
        if not user:
            existing_user = get_user_by_email(db, email)
            if existing_user:
                # Email đã đăng ký bằng mật khẩu -> liên kết Google vào tài khoản đó
                if existing_user.google_id and existing_user.google_id != google_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Email đã được liên kết với một tài khoản Google khác"
                    )
                user = link_google_account(db, existing_user, google_id)
                if not user.is_verified:
                    user.is_verified = True
            else:
                user = create_user(
                    db=db,
                    full_name=google_data["fullName"],
                    email=email,
                    password_hash=None,
                    region=None,
                    account_type="personal",
                    store_name=None,
                    business_type=DEFAULT_GOOGLE_BUSINESS_TYPE,
                    google_id=google_id,
                    role=Roles.USER,
                    is_verified=True
                )

        if not user.business_type:
            user.business_type = DEFAULT_GOOGLE_BUSINESS_TYPE

        # Tài khoản đang khóa (sai mật khẩu / admin khóa) không vào được bằng Google
        if is_locked(user):
            raise locked_error(user)

        session = create_session(db, user)
        db.commit()
        db.refresh(user)

        return {
            "success": True,
            **session,
            "user": user_to_dict(user)
        }
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tài khoản Google đã tồn tại"
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng nhập bằng Google"
        )


def refresh_access_token(db: Session, token: str):
    try:
        result = rotate_refresh_token(db=db, token=token)
        user = get_user_by_id(db, result["userId"])

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Người dùng không tồn tại"
            )

        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản chưa được xác thực"
            )

        access = create_access_session(user)
        # Tự động dọn dẹp các token hết hạn / revoked thừa trong database
        purge_expired_refresh_tokens(db)
        db.commit()

        return {
            "success": True,
            **access,
            "refreshToken": result["refreshToken"]
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể làm mới phiên đăng nhập"
        )


def logout_user(db: Session, token: str):
    try:
        revoke_refresh_token_value(db=db, token=token)
        # Xóa cứng các token hết hạn / revoked để tránh lưu dữ liệu dư thừa
        purge_expired_refresh_tokens(db)
        db.commit()
        return {
            "success": True,
            "message": "Đăng xuất thành công"
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng xuất"
        )


def get_current_user(db: Session, payload: dict):
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại"
        )

    return {
        "success": True,
        "user": user_to_dict(user)
    }
