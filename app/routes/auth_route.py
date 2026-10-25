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
    VerifyForgotOTPRequest,
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


# VERIFY FORGOT PASSWORD OTP (ALIAS CHO MOBILE)
@router.post("/verify-forgot-otp")
def verify_forgot_otp(
    request: VerifyForgotOTPRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Alias xác thực OTP quên mật khẩu (Bước 2):
    Ép purpose = 'forgot_password', gọi chung verify_otp_controller và trả về reset_token.
    """
    verify_req = VerifyOTPRequest(
        email=request.email,
        code=request.code,
        purpose="forgot_password"
    )
    return verify_otp_controller(
        request=verify_req,
        response=response,
        db=db
    )


# FORGOT PASSWORD / RESET PASSWORD
@router.post("/forgot-password")
@router.post("/reset-password")
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


# CURRENT USER PERMISSIONS (frontend dùng để ẩn/hiện chức năng)
@router.get("/me/permissions")
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


# PROFILE DETAILS (ALIAS TO /me)
@router.get("/profile")
def profile(
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(get_db)
):
    return me_controller(
        payload=payload,
        db=db
    )


# CHANGE PASSWORD
@router.post("/change-password")
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
@router.put("/profile")
@router.patch("/profile")
@router.put("/me")
@router.patch("/me")
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
