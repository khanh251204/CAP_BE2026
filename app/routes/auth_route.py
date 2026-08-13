from fastapi import (
    APIRouter,
    Depends,
    status
)

from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import authenticate_user

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

from app.controllers.auth_controller import (
    register_controller,
    login_controller,
    me_controller,
    verify_otp_controller,
    send_otp_controller,
    refresh_token_controller,
    logout_controller,
    forgot_password_controller,
    verify_reset_otp_controller,
    reset_password_controller,
    google_login_controller
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


# REGISTER
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    return register_controller(
        request=request,
        db=db
    )


# SEND / RESEND VERIFY EMAIL OTP
@router.post("/send-otp")
def send_otp(
    request: SendOTPRequest,
    db: Session = Depends(get_db)
):
    return send_otp_controller(
        request=request,
        db=db
    )


# VERIFY EMAIL OTP
@router.post("/verify-otp")
def verify_otp(
    request: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    return verify_otp_controller(
        request=request,
        db=db
    )


# FORGOT PASSWORD
@router.post("/forgot-password")
def forgot_password_route(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    return forgot_password_controller(
        request=request,
        db=db
    )


# VERIFY RESET OTP
@router.post("/verify-reset-otp")
def verify_reset_otp(
    request: VerifyResetOTPRequest,
    db: Session = Depends(get_db)
):
    return verify_reset_otp_controller(
        request=request,
        db=db
    )


# RESET PASSWORD
@router.post("/reset-password")
def reset_password_route(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    return reset_password_controller(
        request=request,
        db=db
    )


# LOGIN
@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    return login_controller(
        request=request,
        db=db
    )


# GOOGLE LOGIN
@router.post("/google")
def google_login_route(
    request: GoogleLoginRequest,
    db: Session = Depends(get_db)
):
    return google_login_controller(
        request=request,
        db=db
    )


# REFRESH TOKEN
@router.post("/refresh-token")
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    return refresh_token_controller(
        request=request,
        db=db
    )


# LOGOUT
@router.post("/logout")
def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db)
):
    return logout_controller(
        request=request,
        db=db
    )


# CURRENT USER
@router.get("/me")
def me(
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(get_db)
):
    return me_controller(
        payload=payload,
        db=db
    )