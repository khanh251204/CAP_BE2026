import os

from dotenv import load_dotenv
from fastapi import Response


load_dotenv()


# ============================================================
# COOKIE CONFIGURATION
# ============================================================

JWT_ACCESS_COOKIE_NAME = os.getenv(
    "JWT_ACCESS_COOKIE_NAME",
    "access_token"
)

JWT_REFRESH_COOKIE_NAME = os.getenv(
    "JWT_REFRESH_COOKIE_NAME",
    "refresh_token"
)

JWT_RESET_COOKIE_NAME = os.getenv(
    "JWT_RESET_COOKIE_NAME",
    "reset_token"
)


JWT_COOKIE_HTTPONLY = (
    os.getenv(
        "JWT_COOKIE_HTTPONLY",
        "true"
    ).lower()
    == "true"
)


JWT_COOKIE_SECURE = (
    os.getenv(
        "JWT_COOKIE_SECURE",
        "false"
    ).lower()
    == "true"
)


JWT_COOKIE_SAMESITE = os.getenv(
    "JWT_COOKIE_SAMESITE",
    "lax"
)


ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "5"
    )
)


REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv(
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "15"
    )
)


PASSWORD_RESET_EXPIRE_MINUTES = int(
    os.getenv(
        "PASSWORD_RESET_EXPIRE_MINUTES",
        "10"
    )
)


# ============================================================
# ACCESS COOKIE
# ============================================================

def set_access_cookie(
    response: Response,
    token: str
):
    response.set_cookie(
        key=JWT_ACCESS_COOKIE_NAME,
        value=token,
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )


# ============================================================
# REFRESH COOKIE
# ============================================================

def set_refresh_cookie(
    response: Response,
    token: str
):
    response.set_cookie(
        key=JWT_REFRESH_COOKIE_NAME,
        value=token,
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1"
    )


# ============================================================
# RESET COOKIE
# ============================================================

def set_reset_cookie(
    response: Response,
    token: str
):
    response.set_cookie(
        key=JWT_RESET_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE,
        max_age=PASSWORD_RESET_EXPIRE_MINUTES * 60,
        path="/api/v1"
    )


# ============================================================
# DELETE ACCESS COOKIE
# ============================================================

def delete_access_cookie(
    response: Response
):
    response.delete_cookie(
        key=JWT_ACCESS_COOKIE_NAME,
        path="/",
        secure=JWT_COOKIE_SECURE,
        httponly=JWT_COOKIE_HTTPONLY,
        samesite=JWT_COOKIE_SAMESITE
    )


# ============================================================
# DELETE REFRESH COOKIE
# ============================================================

def delete_refresh_cookie(
    response: Response
):
    response.delete_cookie(
        key=JWT_REFRESH_COOKIE_NAME,
        path="/api/v1",
        secure=JWT_COOKIE_SECURE,
        httponly=JWT_COOKIE_HTTPONLY,
        samesite=JWT_COOKIE_SAMESITE
    )


# ============================================================
# DELETE RESET COOKIE
# ============================================================

def delete_reset_cookie(
    response: Response
):
    response.delete_cookie(
        key=JWT_RESET_COOKIE_NAME,
        path="/api/v1",
        secure=JWT_COOKIE_SECURE,
        httponly=True,
        samesite=JWT_COOKIE_SAMESITE
    )


# ============================================================
# DELETE AUTH COOKIES
# ============================================================

def delete_auth_cookies(
    response: Response
):
    delete_access_cookie(response)
    delete_refresh_cookie(response)


# ============================================================
# DELETE ALL COOKIES
# ============================================================

def delete_all_cookies(
    response: Response
):
    delete_access_cookie(response)
    delete_refresh_cookie(response)
    delete_reset_cookie(response)