from datetime import (
    datetime,
    timedelta,
    timezone
)

import hashlib
import hmac
import os

from dotenv import load_dotenv

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from jose import (
    jwt,
    JWTError,
    ExpiredSignatureError
)

from app.configs.cookie import (
    JWT_ACCESS_COOKIE_NAME
)


load_dotenv()


SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY"
)

ALGORITHM = os.getenv(
    "JWT_ALGORITHM",
    "HS256"
)

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "15"
    )
)

PASSWORD_RESET_EXPIRE_MINUTES = int(
    os.getenv(
        "PASSWORD_RESET_EXPIRE_MINUTES",
        "10"
    )
)


if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY chÆ°a Ä‘Æ°á»£c cáº¥u hÃ¬nh trong .env"
    )


bearer_scheme = HTTPBearer(
    auto_error=False
)


# PASSWORD FINGERPRINT
def create_password_fingerprint(
    password_hash: str
) -> str:
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        password_hash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ACCESS TOKEN
def create_access_token(
    data: dict
) -> str:
    to_encode = data.copy()

    expire = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# DECODE ACCESS TOKEN
def decode_access_token(
    token: str
) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[
                ALGORITHM
            ]
        )

        if (
            payload.get("type")
            != "access"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token khÃ´ng há»£p lá»‡"
            )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token khÃ´ng há»£p lá»‡"
            )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Ä‘Ã£ háº¿t háº¡n"
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token khÃ´ng há»£p lá»‡"
        )


# PASSWORD RESET TOKEN
def create_reset_token(
    user_id: int,
    email: str,
    password_hash: str
) -> str:
    expire = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=PASSWORD_RESET_EXPIRE_MINUTES
        )
    )

    password_fingerprint = (
        create_password_fingerprint(
            password_hash
        )
    )

    payload = {
        "sub": str(
            user_id
        ),
        "email": email,
        "type": "password_reset",
        "passwordFingerprint": (
            password_fingerprint
        ),
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# DECODE RESET TOKEN
def decode_reset_token(
    token: str
) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[
                ALGORITHM
            ]
        )

        if (
            payload.get("type")
            != "password_reset"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token khÃ´ng há»£p lá»‡"
            )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token khÃ´ng há»£p lá»‡"
            )

        if not payload.get("email"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token khÃ´ng há»£p lá»‡"
            )

        if not payload.get(
            "passwordFingerprint"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token khÃ´ng há»£p lá»‡"
            )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token Ä‘Ã£ háº¿t háº¡n"
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token khÃ´ng há»£p lá»‡"
        )


# AUTHENTICATION
def authenticate_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    )
):
    token = request.cookies.get(
        JWT_ACCESS_COOKIE_NAME
    )

    # Fallback Bearer Token
    if (
        not token
        and credentials
    ):
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Báº¡n chÆ°a Ä‘Äƒng nháº­p"
        )

    return decode_access_token(
        token
    )


# AUTHORIZATION
def authorize_roles(
    *roles
):
    def wrapper(
        user=Depends(
            authenticate_user
        )
    ):
        if (
            user.get("role")
            not in roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Báº¡n khÃ´ng cÃ³ quyá»n truy cáº­p"
            )

        return user

    return wrapper


def get_current_user_id(
    payload: dict = Depends(authenticate_user)
) -> int:
    return int(payload["sub"])
