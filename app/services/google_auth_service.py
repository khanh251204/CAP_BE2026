import os
import requests as requests_lib

from dotenv import load_dotenv

from fastapi import (
    HTTPException,
    status,
)

from google.oauth2 import id_token
from google.auth.transport import requests


load_dotenv()


GOOGLE_WEB_CLIENT_ID = os.getenv(
    "GOOGLE_WEB_CLIENT_ID"
)

GOOGLE_CLIENT_SECRET = os.getenv(
    "GOOGLE_CLIENT_SECRET"
)


# ============================================================
# EXCHANGE AUTHORIZATION CODE
# ============================================================

def exchange_code_for_id_token(
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
) -> str:
    """
    Trao đổi Authorization Code để lấy ID Token.
    """

    if not GOOGLE_WEB_CLIENT_ID:
        raise RuntimeError(
            "Chưa cấu hình GOOGLE_WEB_CLIENT_ID"
        )

    if not GOOGLE_CLIENT_SECRET:
        raise RuntimeError(
            "Chưa cấu hình GOOGLE_CLIENT_SECRET"
        )

    url = "https://oauth2.googleapis.com/token"

    payload = {
        "code": code,
        "client_id": GOOGLE_WEB_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    if code_verifier:
        payload["code_verifier"] = code_verifier

    try:
        response = requests_lib.post(
            url,
            data=payload,
            timeout=10
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Không thể kết nối đến máy chủ "
                "Google OAuth"
            ),
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                f"Lỗi khi trao đổi mã Google: "
                f"{response.text}"
            ),
        )

    data = response.json()

    id_token_val = data.get(
        "id_token"
    )

    if not id_token_val:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google không trả về ID Token",
        )

    return id_token_val


# ============================================================
# VERIFY GOOGLE ID TOKEN
# ============================================================

def verify_google_id_token(
    token: str,
) -> dict:
    """
    Xác thực Google ID Token.

    Kiểm tra:
    - Chữ ký Google
    - Thời hạn token
    - Audience
    - Issuer
    - Google user ID
    - Email
    - Email đã được xác thực
    """

    if not GOOGLE_WEB_CLIENT_ID:
        raise RuntimeError(
            "Chưa cấu hình GOOGLE_WEB_CLIENT_ID"
        )

    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID Token không được để trống",
        )

    try:
        payload = id_token.verify_oauth2_token(
            token.strip(),
            requests.Request(),
            GOOGLE_WEB_CLIENT_ID,
            clock_skew_in_seconds=60,
        )

    except ValueError as exc:
        print(
            "GOOGLE TOKEN VERIFICATION ERROR DETAILS:",
            str(exc)
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Google ID Token không hợp lệ: "
                f"{str(exc)}"
            ),
        ) from exc

    # ========================================================
    # CHECK ISSUER
    # ========================================================

    issuer = payload.get(
        "iss"
    )

    if issuer not in {
        "accounts.google.com",
        "https://accounts.google.com",
    }:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token không hợp lệ",
        )

    # ========================================================
    # GET GOOGLE DATA
    # ========================================================

    google_id = payload.get(
        "sub"
    )

    email = payload.get(
        "email"
    )

    email_verified = payload.get(
        "email_verified"
    )

    # ========================================================
    # CHECK GOOGLE USER ID
    # ========================================================

    if not google_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token thiếu user ID",
        )

    # ========================================================
    # CHECK EMAIL
    # ========================================================

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token thiếu email",
        )

    # ========================================================
    # CHECK EMAIL VERIFIED
    # ========================================================

    if email_verified is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email Google chưa được xác thực",
        )

    # ========================================================
    # RETURN GOOGLE USER DATA
    # ========================================================

    return {
        "googleId": google_id,

        "email": (
            email.strip().lower()
        ),

        "fullName": (
            payload.get("name")
            or email.split("@")[0]
        ),

        "picture": payload.get(
            "picture"
        ),
    }