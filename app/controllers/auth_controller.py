from sqlalchemy.orm import Session

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    VerifyOTPRequest,
    SendOTPRequest,
    RefreshTokenRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    VerifyResetOTPRequest,
    ResetPasswordRequest,
    GoogleLoginRequest
)

from app.services.auth_service import (
    register_user,
    login_user,
    get_current_user,
    verify_email_otp,
    send_verify_email_otp,
    refresh_access_token,
    logout_user,
    forgot_password,
    verify_reset_password_otp,
    reset_password,
    google_login
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


# SEND / RESEND VERIFY EMAIL OTP
def send_otp_controller(
    request: SendOTPRequest,
    db: Session
):
    return send_verify_email_otp(
        db=db,
        data=request
    )


# VERIFY EMAIL OTP
def verify_otp_controller(
    request: VerifyOTPRequest,
    db: Session
):
    return verify_email_otp(
        db=db,
        data=request
    )


# FORGOT PASSWORD
def forgot_password_controller(
    request: ForgotPasswordRequest,
    db: Session
):
    return forgot_password(
        db=db,
        data=request
    )


# VERIFY RESET OTP
def verify_reset_otp_controller(
    request: VerifyResetOTPRequest,
    db: Session
):
    return verify_reset_password_otp(
        db=db,
        data=request
    )


# RESET PASSWORD
def reset_password_controller(
    request: ResetPasswordRequest,
    db: Session
):
    return reset_password(
        db=db,
        data=request
    )


# LOGIN
def login_controller(
    request: LoginRequest,
    db: Session
):
    return login_user(
        db=db,
        data=request
    )


# GOOGLE LOGIN
def google_login_controller(
    request: GoogleLoginRequest,
    db: Session
):
    return google_login(
        db=db,
        data=request
    )


# REFRESH TOKEN
def refresh_token_controller(
    request: RefreshTokenRequest,
    db: Session
):
    return refresh_access_token(
        db=db,
        data=request
    )


# LOGOUT
def logout_controller(
    request: LogoutRequest,
    db: Session
):
    return logout_user(
        db=db,
        data=request
    )


# CURRENT USER
def me_controller(
    payload: dict,
    db: Session
):
    return get_current_user(
        db=db,
        payload=payload
    )