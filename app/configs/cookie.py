import os

from dotenv import load_dotenv
from fastapi import Response


load_dotenv()


JWT_ACCESS_COOKIE_NAME = os.getenv(
    "JWT_ACCESS_COOKIE_NAME",
    "access_token"
)

JWT_COOKIE_NAME = os.getenv(
    "JWT_COOKIE_NAME",
    "refresh_token"
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
        path="/api/auth"
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
        path="/api/auth",
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