from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Response,
    status,
    Request,
    HTTPException
)
from pydantic import BaseModel


from fastapi.responses import RedirectResponse, HTMLResponse

from sqlalchemy.orm import Session

from app.configs.cookie import (
    JWT_REFRESH_COOKIE_NAME,
    set_access_cookie,
    set_refresh_cookie
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

from app.services.google_auth_service import (
    exchange_code_for_id_token
)

from app.services.auth_service import (
    google_login
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Authentication"]
)


# ============================================================
# REGISTER
# ============================================================

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


# ============================================================
# SEND OTP
# ============================================================

@router.post("/send-otp")
def send_otp(
    request: SendOTPRequest,
    db: Session = Depends(get_db)
):
    return send_otp_controller(
        request=request,
        db=db
    )


# ============================================================
# VERIFY OTP
# ============================================================

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


# ============================================================
# RESET PASSWORD
# ============================================================

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    response: Response,
    http_request: Request,
    db: Session = Depends(get_db)
):
    return reset_password_controller(
        request=request,
        response=response,
        http_request=http_request,
        db=db
    )


# ============================================================
# LOGIN
# ============================================================

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


# ============================================================
# GOOGLE LOGIN
# ============================================================

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

# ============================================================
# GOOGLE LOGIN CALLBACK
# ============================================================

@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    try:

        print("\n================ GOOGLE CALLBACK ================")
        print("CODE:", code[:20] + "..." if code else None)
        print("STATE:", state)

        # ----------------------------------------------------
        # BUILD REDIRECT URI
        # ----------------------------------------------------

        scheme = request.headers.get(
            "x-forwarded-proto",
            request.url.scheme
        )

        host = request.headers.get(
            "x-forwarded-host",
            request.url.netloc
        )

        redirect_uri = (
            f"{scheme}://{host}"
            f"/api/v1/google/callback"
        )

        print("REDIRECT URI:", redirect_uri)

        # ----------------------------------------------------
        # READ STATE
        # ----------------------------------------------------

        parts = state.split("|")

        local_redirect = parts[0]

        code_verifier = (
            parts[1]
            if len(parts) > 1
            else None
        )

        print("LOCAL REDIRECT:", local_redirect)
        print(
            "CODE VERIFIER:",
            "EXISTS" if code_verifier else "NONE"
        )

        # ----------------------------------------------------
        # EXCHANGE CODE
        # ----------------------------------------------------

        print("STEP 1: EXCHANGING GOOGLE CODE...")

        id_token_val = exchange_code_for_id_token(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri
        )

        print("STEP 1 SUCCESS: GOOGLE TOKEN RECEIVED")

        # ----------------------------------------------------
        # GOOGLE LOGIN
        # ----------------------------------------------------

        print("STEP 2: GOOGLE LOGIN...")

        login_req = GoogleLoginRequest(
            idToken=id_token_val
        )

        result = google_login(
            db=db,
            data=login_req
        )

        print("STEP 2 SUCCESS: USER LOGIN SUCCESS")
        print("USER:", result["user"]["email"])

        # ----------------------------------------------------
        # REDIRECT TO FE WITH COOKIES SET
        # ----------------------------------------------------

        redirect_url = (
            f"{local_redirect}?success=true"
        )

        print(
            "REDIRECT SUCCESS:",
            redirect_url
        )

        print("==================================================\n")

        html_content = f"""
        <html>
        <head>
            <script>
                window.location.href = "{redirect_url}";
            </script>
        </head>
        <body>
            <p>Redirecting to app...</p>
        </body>
        </html>
        """
        response = HTMLResponse(content=html_content)

        set_access_cookie(
            response=response,
            token=result["accessToken"]
        )

        set_refresh_cookie(
            response=response,
            token=result["refreshToken"]
        )

        return response

    except Exception as e:

        import traceback
        import urllib.parse

        print("\n================ GOOGLE CALLBACK ERROR ================")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))

        traceback.print_exc()

        local_redirect = (
            state.split("|")[0]
            if state
            else "exp://localhost:8081"
        )

        encoded_message = urllib.parse.quote(str(e))
        redirect_url = (
            f"{local_redirect}?success=false&message={encoded_message}"
        )

        print(
            "REDIRECT ERROR:",
            redirect_url
        )

        print("=======================================================\n")

        html_content = f"""
        <html>
        <head>
            <script>
                window.location.href = "{redirect_url}";
            </script>
        </head>
        <body>
            <p>Error redirecting to app...</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)


# ============================================================
# REFRESH TOKEN
# ============================================================

@router.post("/refresh-token")
def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=JWT_REFRESH_COOKIE_NAME
    ),
    db: Session = Depends(get_db)
):
    # Try to get refresh token from headers if not found in cookie
    if not refresh_token:
        refresh_token = request.headers.get("x-refresh-token")

        # Fallback to Authorization header if it contains Bearer
        if not refresh_token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                refresh_token = auth_header.split(" ")[1]

    return refresh_token_controller(
        token=refresh_token,
        response=response,
        db=db
    )


# ============================================================
# LOGOUT
# ============================================================

@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=JWT_REFRESH_COOKIE_NAME
    ),
    db: Session = Depends(get_db)
):
    return logout_controller(
        token=refresh_token,
        response=response,
        db=db
    )


# ============================================================
# CURRENT USER
# ============================================================

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


# ============================================================
# UPDATE PROFILE
# ============================================================

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