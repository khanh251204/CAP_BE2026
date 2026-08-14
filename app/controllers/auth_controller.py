from sqlalchemy.orm import Session

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    RefreshTokenRequest,
    GoogleLoginRequest
)

from app.services.auth_service import (
    register_user,
    login_user,
    send_auth_otp,
    verify_auth_otp,
    reset_password,
    google_login,
    refresh_access_token,
    logout_user,
    get_current_user
)


# REGISTER
def register_controller(
    request: RegisterRequest,
    db: Session
):
    return register_user(
        db,
        request
    )


# SEND OTP
def send_otp_controller(
    request: SendOTPRequest,
    db: Session
):
    return send_auth_otp(
        db,
        request
    )


# VERIFY OTP
def verify_otp_controller(
    request: VerifyOTPRequest,
    db: Session
):
    return verify_auth_otp(
        db,
        request
    )


# RESET PASSWORD
def reset_password_controller(
    request: ResetPasswordRequest,
    db: Session
):
    return reset_password(
        db,
        request
    )


# LOGIN
def login_controller(
    request: LoginRequest,
    db: Session
):
    return login_user(
        db,
        request
    )


# GOOGLE
def google_login_controller(
    request: GoogleLoginRequest,
    db: Session
):
    return google_login(
        db,
        request
    )


# REFRESH
def refresh_token_controller(
    request: RefreshTokenRequest,
    db: Session
):
    return refresh_access_token(
        db,
        request
    )


# LOGOUT
def logout_controller(
    request: RefreshTokenRequest,
    db: Session
):
    return logout_user(
        db,
        request
    )


# ME
def me_controller(
    payload: dict,
    db: Session
):
    return get_current_user(
        db,
        payload
    )