import os
from fastapi import Response
from app.configs.settings import settings


JWT_ACCESS_COOKIE_NAME = settings.JWT_ACCESS_COOKIE_NAME
JWT_COOKIE_NAME = settings.JWT_COOKIE_NAME
JWT_COOKIE_HTTPONLY = settings.JWT_COOKIE_HTTPONLY

# Đặt JWT_COOKIE_SECURE = True khi ENVIRONMENT == "production" hoặc APP_ENV == "production"
_env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or settings.APP_ENV or "").strip().lower()
JWT_COOKIE_SECURE = True if _env == "production" else settings.cookie_secure

JWT_COOKIE_SAMESITE = settings.JWT_COOKIE_SAMESITE
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


# ACCESS COOKIE
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
        max_age=(
            ACCESS_TOKEN_EXPIRE_MINUTES
            * 60
        ),
        path="/"
    )


# REFRESH COOKIE
def set_refresh_cookie(
    response: Response,
    token: str
):
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE,
        max_age=(
            REFRESH_TOKEN_EXPIRE_DAYS
            * 24
            * 60
            * 60
        ),
        path="/api/v1"
    )


# DELETE ACCESS COOKIE
def delete_access_cookie(
    response: Response
):
    response.delete_cookie(
        key=JWT_ACCESS_COOKIE_NAME,
        path="/",
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE
    )


# DELETE REFRESH COOKIE
def delete_refresh_cookie(
    response: Response
):
    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/api/v1",
        httponly=JWT_COOKIE_HTTPONLY,
        secure=JWT_COOKIE_SECURE,
        samesite=JWT_COOKIE_SAMESITE
    )


def delete_auth_cookies(
    response: Response
):
    delete_access_cookie(
        response
    )

    delete_refresh_cookie(
        response
    )