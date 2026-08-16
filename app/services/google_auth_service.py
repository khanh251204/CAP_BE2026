import os

from dotenv import load_dotenv

from fastapi import (
    HTTPException,
    status
)

from google.oauth2 import id_token
from google.auth.transport import requests


load_dotenv()


GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID"
)

GOOGLE_WEB_CLIENT_ID = os.getenv(
    "GOOGLE_WEB_CLIENT_ID"
)

GOOGLE_ANDROID_CLIENT_ID = os.getenv(
    "GOOGLE_ANDROID_CLIENT_ID"
)

GOOGLE_IOS_CLIENT_ID = os.getenv(
    "GOOGLE_IOS_CLIENT_ID"
)


def get_google_client_ids() -> set[str]:
    client_ids = {
        GOOGLE_CLIENT_ID,
        GOOGLE_WEB_CLIENT_ID,
        GOOGLE_ANDROID_CLIENT_ID,
        GOOGLE_IOS_CLIENT_ID
    }

    return {
        client_id
        for client_id in client_ids
        if client_id
    }


def verify_google_id_token(
    token: str
) -> dict:
    """
    Verify Google ID Token.

    Kiểm tra:
    - chữ ký Google
    - exp
    - iss
    - aud
    """

    allowed_client_ids = (
        get_google_client_ids()
    )

    if not allowed_client_ids:
        raise RuntimeError(
            "Chưa cấu hình Google Client ID"
        )

    try:
        # Không truyền audience ở đây
        # vì backend có nhiều client:
        # Android / iOS / Web
        payload = (
            id_token.verify_oauth2_token(
                token,
                requests.Request()
            )
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token không hợp lệ"
        )

    audience = payload.get(
        "aud"
    )

    if audience not in allowed_client_ids:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google Client ID không hợp lệ"
        )

    issuer = payload.get(
        "iss"
    )

    if issuer not in {
        "accounts.google.com",
        "https://accounts.google.com"
    }:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token không hợp lệ"
        )

    google_id = payload.get(
        "sub"
    )

    email = payload.get(
        "email"
    )

    email_verified = payload.get(
        "email_verified"
    )

    if not google_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token thiếu user id"
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token thiếu email"
        )

    if email_verified is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email Google chưa được xác thực"
        )

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
        )
    }