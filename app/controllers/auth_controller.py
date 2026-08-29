from fastapi import (
    HTTPException,
    Request,
    Response,
    status
)

from sqlalchemy.orm import Session

from app.configs.cookie import (
    JWT_RESET_COOKIE_NAME,
    set_access_cookie,
    set_refresh_cookie,
    set_reset_cookie,
    delete_auth_cookies,
    delete_reset_cookie
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


# ============================================================
# SET AUTH COOKIES
# ============================================================

def set_session_cookie(
    response: Response,
    result: dict
):
    access_token = result.get(
        "accessToken"
    )

    refresh_token = result.get(
        "refreshToken"
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


# ============================================================
# REGISTER
# ============================================================

def register_controller(
    request: RegisterRequest,
    db: Session
):
    register_user(
        db=db,
        data=request
    )

    return {
        "success": True
    }


# ============================================================
# SEND OTP
# ============================================================

def send_otp_controller(
    request: SendOTPRequest,
    db: Session
):
    send_auth_otp(
        db=db,
        data=request
    )

    return {
        "success": True
    }


# ============================================================
# VERIFY OTP
# ============================================================

def verify_otp_controller(
    request: VerifyOTPRequest,
    response: Response,
    db: Session
):
    result = verify_auth_otp(
        db=db,
        data=request
    )

    # ========================================================
    # FORGOT PASSWORD
    # ========================================================

    if request.purpose == "forgot_password":

        reset_token = result.get("resetToken")

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Không tạo được Reset Token"
            )

        set_reset_cookie(response=response, token=reset_token)

        return {
            "success": True,
            "message": "Xác thực OTP thành công",
            "nextAction": "reset_password",
            "expiresIn": result.get("expiresIn")
        }

    # ========================================================
    # VERIFY EMAIL
    # ========================================================

    set_session_cookie(
        response=response,
        result=result
    )

    return {
        "success": True
    }


# ============================================================
# RESET PASSWORD
# ============================================================

def reset_password_controller(
    request: ResetPasswordRequest,
    response: Response,
    http_request: Request,
    db: Session
):
    reset_token = http_request.cookies.get(JWT_RESET_COOKIE_NAME)
    if not reset_token:
        reset_token = request.resetToken

    if not reset_token or reset_token == "cookie":
        reset_token = http_request.cookies.get(JWT_RESET_COOKIE_NAME)

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Reset token không tồn tại "
                "hoặc đã hết hạn"
            )
        )

    reset_password(
        db=db,
        data=request,
        reset_token=reset_token
    )

    delete_auth_cookies(
        response=response
    )

    return {
        "success": True,
        "nextAction": "login"
    }


# ============================================================
# LOGIN
# ============================================================

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


# ============================================================
# GOOGLE LOGIN
# ============================================================

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


# ============================================================
# REFRESH TOKEN
# ============================================================

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


# ============================================================
# LOGOUT
# ============================================================

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
        "success": True
    }


# ============================================================
# CURRENT USER
# ============================================================

def me_controller(
    payload: dict,
    db: Session
):
    user = get_current_user(
        db=db,
        payload=payload
    )

    return {
        "success": True,
        "user": user
    }


# ============================================================
# UPDATE PROFILE
# ============================================================

def update_profile_controller(
    request: UpdateProfileRequest,
    payload: dict,
    db: Session
):
    update_profile(
        db=db,
        payload=payload,
        data=request
    )

    return {
        "success": True
    }