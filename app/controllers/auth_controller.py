from sqlalchemy.orm import Session

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    VerifyOTPRequest,
    SendOTPRequest
)

from app.services.auth_service import (
    register_user,
    login_user,
    get_current_user,
    verify_email_otp,
    send_verify_email_otp
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

# VERIFY OTP
def verify_otp_controller(
    request: VerifyOTPRequest,
    db: Session
):
    return verify_email_otp(
        db=db,
        data=request
    )

# SEND / RESEND OTP
def send_otp_controller(
    request: SendOTPRequest,
    db: Session
):
    return send_verify_email_otp(
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

# CURRENT USER
def me_controller(
    payload: dict,
    db: Session
):
    return get_current_user(
        db=db,
        payload=payload
    )