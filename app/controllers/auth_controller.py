from fastapi import (
    HTTPException,
    Response,
    status
)

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.configs.cookie import (
    set_access_cookie,
    set_refresh_cookie,
    delete_auth_cookies
)

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    UpdateProfileRequest,
    GoogleLoginRequest
)

from app.services.auth_service import (
    register_user,
    send_auth_otp,
    verify_auth_otp,
    reset_password,
    change_user_password,
    update_user_profile_service,
    login_user,
    google_login,
    refresh_access_token,
    logout_user,
    get_current_user
)

# SET SESSION COOKIE
def set_session_cookie(
    response: Response,
    result: dict
):
    access_token = result.pop(
        "accessToken",
        None
    )

    refresh_token = result.pop(
        "refreshToken",
        None
    )

    if access_token:
        set_access_cookie(
            response=response,
            token=access_token
        )

    if refresh_token:
        set_refresh_cookie(
            response=response,
            token=refresh_token
        )

# REGISTER
def register_controller(
    request: RegisterRequest,
    db: Session
):
    return register_user(
        db=db,
        data=request
    )


# SEND OTP
def send_otp_controller(
    request: SendOTPRequest,
    db: Session
):
    return send_auth_otp(
        db=db,
        data=request
    )

# VERIFY OTP
def verify_otp_controller(
    request: VerifyOTPRequest,
    response: Response,
    db: Session
):
    result = verify_auth_otp(
        db=db,
        data=request
    )

    if result.get(
        "accessToken"
    ):
        set_session_cookie(
            response=response,
            result=result
        )

        return {
            "success": True
        }

    return result

# RESET PASSWORD / FORGOT PASSWORD
def reset_password_controller(
    request: ResetPasswordRequest,
    db: Session,
    auth_header: str | None = None
):
    if not request.resetToken and auth_header:
        token = auth_header.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if token.lower() not in ("cookie", "undefined", "null"):
            request.resetToken = token

    return reset_password(
        db=db,
        data=request
    )




# FORGOT PASSWORD (ALIAS)
forgot_password_controller = reset_password_controller



# LOGIN
def login_controller(
    request: LoginRequest,
    response: Response,
    db: Session
):
    result = login_user(
        db=db,
        data=request
    )

    set_session_cookie(
        response=response,
        result=result
    )

    return {
        "success": True
    }

# GOOGLE LOGIN
def google_login_controller(
    request: GoogleLoginRequest,
    response: Response,
    db: Session
):
    result = google_login(
        db=db,
        data=request
    )

    set_session_cookie(
        response=response,
        result=result
    )

    return {
        "success": True
    }

# REFRESH TOKEN
def refresh_token_controller(
    token: str | None,
    response: Response,
    db: Session
):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không tồn tại"
        )

    result = refresh_access_token(
        db=db,
        token=token
    )

    set_session_cookie(
        response=response,
        result=result
    )

    return {
        "success": True
    }

# LOGOUT
def logout_controller(
    token: str | None,
    response: Response,
    db: Session
):
    try:
        if token:
            logout_user(
                db=db,
                token=token
            )

    except HTTPException:
        # Refresh token hết hạn / đã revoke
        # vẫn cho phép logout
        db.rollback()

    finally:
        delete_auth_cookies(
            response=response
        )

    return {
        "success": True
    }

# CURRENT USER
def me_controller(
    payload: dict,
    db: Session
):
    return get_current_user(
        db=db,
        payload=payload
    )


# CHANGE PASSWORD
def change_password_controller(
    request: ChangePasswordRequest,
    payload: dict,
    response: Response,
    db: Session
):
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

    result = change_user_password(
        db=db,
        user_id=user_id,
        data=request
    )

    delete_auth_cookies(
        response=response
    )

    return result


# UPDATE PROFILE
def update_profile_controller(
    request: UpdateProfileRequest,
    payload: dict,
    db: Session
):
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

    return update_user_profile_service(
        db=db,
        user_id=user_id,
        data=request
    )
