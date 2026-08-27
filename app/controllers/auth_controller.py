from fastapi import (
    HTTPException,
    Response,
    status
)

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
    GoogleLoginRequest,
    UpdateProfileRequest
)

from app.services.auth_service import (
    register_user,
    send_auth_otp,
    verify_auth_otp,
    reset_password,
    login_user,
    google_login,
    refresh_access_token,
    logout_user,
    get_current_user,
    update_profile
)

# UPDATE PROFILE
def update_profile_controller(
    request: UpdateProfileRequest,
    payload: dict,
    db: Session
):
    return update_profile(
        db=db,
        payload=payload,
        data=request
    )

# SET SESSION COOKIE (Há»— trá»£ cáº£ HttpOnly Cookie vÃ  JSON Response cho Mobile)
def set_session_cookie(
    response: Response,
    result: dict
):
    access_token = result.get("accessToken")
    refresh_token = result.get("refreshToken")

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

    if result.get("accessToken"):
        set_session_cookie(
            response=response,
            result=result
        )

    return result

# RESET PASSWORD
def reset_password_controller(
    request: ResetPasswordRequest,
    response: Response,
    db: Session
):
    result = reset_password(
        db=db,
        data=request
    )

    delete_auth_cookies(
        response=response
    )

    return result

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

    # Tráº£ vá» accessToken, refreshToken, expiresIn, user cho Mobile Client
    return {
        "success": True,
        "accessToken": result.get("accessToken"),
        "refreshToken": result.get("refreshToken"),
        "expiresIn": result.get("expiresIn"),
        "tokenType": result.get("tokenType", "bearer"),
        "user": result.get("user")
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
        "success": True,
        "accessToken": result.get("accessToken"),
        "refreshToken": result.get("refreshToken"),
        "expiresIn": result.get("expiresIn"),
        "tokenType": result.get("tokenType", "bearer"),
        "user": result.get("user")
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
            detail="Refresh token khÃ´ng tá»“n táº¡i"
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
        "success": True,
        "accessToken": result.get("accessToken"),
        "refreshToken": result.get("refreshToken"),
        "expiresIn": result.get("expiresIn"),
        "tokenType": result.get("tokenType", "bearer")
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
        db.rollback()
    finally:
        delete_auth_cookies(
            response=response
        )

    return {
        "success": True,
        "message": "ÄÄƒng xuáº¥t thÃ nh cÃ´ng"
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
