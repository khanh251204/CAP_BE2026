from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Response,
    status
)

from sqlalchemy.orm import Session

from app.configs.cookie import (
    JWT_COOKIE_NAME
)

from app.configs.database import (
    get_db
)

from app.configs.jwt import (
    authenticate_user
)

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    GoogleLoginRequest
)

from app.controllers.auth_controller import (
    register_controller,
    login_controller,
    send_otp_controller,
    verify_otp_controller,
    reset_password_controller,
    google_login_controller,
    refresh_token_controller,
    logout_controller,
    me_controller
)


router = APIRouter()


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


# SEND OTP
@router.post("/send-otp")
def send_otp(
    request: SendOTPRequest,
    db: Session = Depends(get_db)
):
    return send_otp_controller(
        request=request,
        db=db
    )


# VERIFY OTP
@router.post("/verify-otp")
def verify_otp(
    request: VerifyOTPRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    return verify_otp_controller(
        request=request,
        response=response,
        db=db
    )


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    return reset_password_controller(
        request=request,
        response=response,
        db=db
    )
    
# LOGIN
@router.post("/login")
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    return login_controller(
        request=request,
        response=response,
        db=db
    )


# GOOGLE LOGIN
@router.post("/google")
def google_login(
    request: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    return google_login_controller(
        request=request,
        response=response,
        db=db
    )


# REFRESH TOKEN
@router.post("/refresh-token")
def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=JWT_COOKIE_NAME
    ),
    db: Session = Depends(get_db)
):
    return refresh_token_controller(
        token=refresh_token,
        response=response,
        db=db
    )


# LOGOUT
@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=JWT_COOKIE_NAME
    ),
    db: Session = Depends(get_db)
):
    return logout_controller(
        token=refresh_token,
        response=response,
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