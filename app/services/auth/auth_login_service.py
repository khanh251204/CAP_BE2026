from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.notification_controller import NotificationController
from app.configs.jwt import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.configs.roles import Roles
from app.configs.security import verify_password
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_google_id,
)
from app.schemas.auth_schema import LoginRequest, GoogleLoginRequest
from app.services.google_auth_service import verify_google_id_token
from app.services.refresh_token_service import (
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token_value
)
from app.services.auth.auth_registration_service import normalize_email, user_to_dict
from app.services.system_log_service import log_event


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


def login_user(db: Session, data: LoginRequest):
    email = normalize_email(data.email)
    user = get_user_by_email(db, email)

    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        log_event(
            level="WARNING",
            step="AUTH",
            message=f"Login failed: invalid email or password for {email}",
            detail={"reason": "INVALID_CREDENTIALS", "email": email}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác"
        )

    if user.lock_until and user.lock_until > datetime.utcnow():
        log_event(
            level="WARNING",
            step="AUTH",
            message=f"Login blocked: account is locked for {email}",
            detail={"reason": "ACCOUNT_LOCKED", "email": email},
            user_id=user.user_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị tạm khóa. Vui lòng liên hệ quản trị viên."
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

    try:
        session = create_session(db, user)
        db.commit()
        db.refresh(user)

        NotificationController.create_notification({
            "userId": str(user.user_id),
            "title": "Đăng nhập thành công 👋",
            "description": f"Chào mừng {user.full_name} quay trở lại VoiceCashBook!",
            "icon": "check",
            "iconColor": "#FFFFFF",
            "borderColor": "#20D66B",
            "notificationType": "login",
            "isRead": False
        })

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
        print("❌ Login error:", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng nhập"
        )


def google_login(db: Session, data: GoogleLoginRequest):
    google_data = verify_google_id_token(data.idToken)
    google_id = google_data["googleId"]
    email = normalize_email(google_data["email"])

    try:
        user = get_user_by_google_id(db, google_id)
        if not user:
            existing_user = get_user_by_email(db, email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email đã tồn tại. Vui lòng đăng nhập bằng mật khẩu."
                )

            user = create_user(
                db=db,
                full_name=google_data["fullName"],
                email=email,
                password_hash=None,
                region=None,
                account_type="personal",
                store_name=None,
                business_type=None,
                google_id=google_id,
                role=Roles.USER,
                is_verified=True
            )

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
