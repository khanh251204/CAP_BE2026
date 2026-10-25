from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status
)

# pyrefly: ignore [missing-import]
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
    ForgotPasswordRequest,
    ChangePasswordRequest,
    UpdateProfileRequest,
    GoogleLoginRequest
)


from app.controllers.auth_controller import (
    register_controller,
    login_controller,
    send_otp_controller,
    verify_otp_controller,
    reset_password_controller,
    forgot_password_controller,
    change_password_controller,
    update_profile_controller,
    google_login_controller,
    refresh_token_controller,
    logout_controller,
    me_controller
)


# /auth/*      : đăng ký, đăng nhập, token, OTP, đặt lại mật khẩu (công khai)
# /users/me/*  : tài nguyên của chính người dùng đang đăng nhập
router = APIRouter(prefix="/auth", tags=["Auth"])
me_router = APIRouter(prefix="/users/me", tags=["Current User"])


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
@router.post("/otp")
def send_otp(
    request: SendOTPRequest,
    db: Session = Depends(get_db)
):
    return send_otp_controller(
        request=request,
        db=db
    )


# VERIFY OTP
@router.post("/otp/verification")
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


# FORGOT PASSWORD / RESET PASSWORD
@router.post("/password-reset")
def forgot_password(
    request: ForgotPasswordRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
):
    auth_header = request_obj.headers.get("authorization")
    return forgot_password_controller(
        request=request,
        db=db,
        auth_header=auth_header
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
@router.post("/refresh")
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
@me_router.get("")
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


# CURRENT USER PERMISSIONS (frontend dùng để ẩn/hiện chức năng)
@me_router.get("/permissions")
def my_permissions(
    payload: dict = Depends(
        authenticate_user
    )
):
    from app.configs.permissions import PERMISSION_CODES
    from app.services.permission_service import PermissionService

    access = PermissionService.get_user_access(int(payload["sub"]))
    if not access.exists:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại hoặc phiên đăng nhập đã hết hạn")
    return {
        "user_id": access.user_id,
        "role": access.role_name,
        "is_admin": access.is_admin,
        # ADMIN có toàn quyền -> trả đủ danh sách để frontend không phải xử lý riêng
        "permissions": sorted(PERMISSION_CODES if access.is_admin else access.permissions),
    }


# CHANGE PASSWORD
@me_router.put("/password")
def change_password(
    request: ChangePasswordRequest,
    response: Response,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(get_db)
):
    return change_password_controller(
        request=request,
        payload=payload,
        response=response,
        db=db
    )


# UPDATE PROFILE
@me_router.patch("")
def update_profile(
    request: UpdateProfileRequest,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(get_db)
):
    return update_profile_controller(
        request=request,
        payload=payload,
        db=db
    )
