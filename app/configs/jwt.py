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

# ENV
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
        "JWT_SECRET_KEY chưa được cấu hình trong .env"
    )


bearer_scheme = HTTPBearer()

# PASSWORD FINGERPRINT
def create_password_fingerprint(
    password_hash: str
) -> str:
    """
    Tạo fingerprint từ password_hash.

    Dùng để làm Reset Token chỉ sử dụng được
    khi password hiện tại chưa bị thay đổi.

    Sau khi reset password thành công:
    password_hash thay đổi
        ↓
    fingerprint thay đổi
        ↓
    Reset Token cũ tự động mất hiệu lực.
    """

    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        password_hash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

# ACCESS TOKEN
def create_access_token(
    data: dict
) -> str:
    """
    Tạo JWT Access Token.
    """

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
    """
    Decode Access Token.
    """

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
                detail="Token không hợp lệ"
            )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ"
            )

        return payload

    except ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn"
        )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

# PASSWORD RESET TOKEN
def create_reset_token(
    user_id: int,
    email: str,
    password_hash: str
) -> str:
    """
    Tạo Reset Token sau khi OTP quên mật khẩu
    được xác thực thành công.

    Reset Token gắn với password_hash hiện tại.
    """

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
    """
    Decode Password Reset Token.
    """

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
                detail="Reset token không hợp lệ"
            )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token không hợp lệ"
            )

        if not payload.get("email"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token không hợp lệ"
            )

        if not payload.get(
            "passwordFingerprint"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reset token không hợp lệ"
            )

        return payload

    except ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token đã hết hạn"
        )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

# AUTHENTICATION
def authenticate_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    )
):
    """
    Dependency lấy Access Token từ:

    Authorization: Bearer <token>
    """

    token = credentials.credentials

    return decode_access_token(
        token
    )

# AUTHORIZATION
def authorize_roles(
    *roles
):
    """
    Kiểm tra quyền role.

    Ví dụ:

    Depends(
        authorize_roles("admin")
    )
    """

    def wrapper(
        user=Depends(
            authenticate_user
        )
    ):
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bạn chưa đăng nhập"
            )

        if (
            user.get("role")
            not in roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập"
            )

        return user

    return wrapper