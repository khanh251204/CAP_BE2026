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
    GoogleLoginRequest,
    UpdateProfileRequest
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
    me_controller,
    update_profile_controller
)

router = APIRouter(
    prefix="/api/v1",
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
def google_login_route(
    request: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    return google_login_controller(
        request=request,
        response=response,
        db=db
    )


from fastapi.responses import RedirectResponse
from fastapi import Request
from app.services.google_auth_service import exchange_code_for_id_token
from app.services.auth_service import google_login

# GOOGLE LOGIN CALLBACK (DIRECT REDIRECT FLOW FOR EXPO GO)
@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    try:
        # Construct the redirect URI dynamically to match the current domain (e.g. cloudflare tunnel)
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.netloc)
        redirect_uri = f"{scheme}://{host}/api/v1/google/callback"

        parts = state.split("|")
        local_redirect = parts[0]
        code_verifier = parts[1] if len(parts) > 1 else None

        id_token_val = exchange_code_for_id_token(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri
        )

        login_req = GoogleLoginRequest(idToken=id_token_val)
        result = google_login(db=db, data=login_req)

        access_token = result.get("accessToken")
        refresh_token = result.get("refreshToken")

        redirect_url = f"{local_redirect}?accessToken={access_token}&refreshToken={refresh_token}&success=true"
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        import traceback
        traceback.print_exc()
        local_redirect = state.split("|")[0] if state else "exp://localhost:8081"
        redirect_url = f"{local_redirect}?error={str(e)}&success=false"
        return RedirectResponse(url=redirect_url)


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

# UPDATE PROFILE
@router.patch("/me")
def update_me(
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