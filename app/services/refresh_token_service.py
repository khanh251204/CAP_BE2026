import os
import hmac
import hashlib
import uuid

from datetime import (
    datetime,
    timedelta,
    timezone
)

from dotenv import load_dotenv
from fastapi import (
    HTTPException,
    status
)

from jose import (
    jwt,
    JWTError,
    ExpiredSignatureError
)

from sqlalchemy.orm import Session

from app.configs.jwt import (
    SECRET_KEY,
    ALGORITHM
)

from app.repositories.refresh_token_repository import (
    create_refresh_token as create_refresh_token_record,
    get_refresh_token_by_jti,
    get_active_refresh_token_by_jti,
    revoke_refresh_token
)

# ENV
load_dotenv()


REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv(
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "30"
    )
)

# HASH REFRESH TOKEN
def hash_refresh_token(
    token: str
) -> str:
    """
    Hash refresh token báº±ng SHA256.

    Database chá»‰ lÆ°u hash,
    khÃ´ng lÆ°u token plaintext.
    """

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

# CREATE REFRESH TOKEN
def create_refresh_token(
    db: Session,
    *,
    user_id: int,
    email: str,
    role: str
) -> str:
    """
    Táº¡o JWT Refresh Token vÃ  lÆ°u hash vÃ o DB.

    Refresh token chá»©a:
    - sub
    - email
    - role
    - jti
    - type=refresh
    - exp

    KhÃ´ng commit táº¡i Ä‘Ã¢y.
    """

    # ID duy nháº¥t cho refresh token
    jti = str(
        uuid.uuid4()
    )

    # Thá»i gian hiá»‡n táº¡i UTC
    now = datetime.now(
        timezone.utc
    )

    expires_at_utc = (
        now
        + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
    )

    # JWT PAYLOAD
    payload = {
        "sub": str(
            user_id
        ),

        "email": email,

        "role": role,

        "jti": jti,

        "type": "refresh",

        "exp": expires_at_utc
    }

    # CREATE JWT
    refresh_token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    # HASH TOKEN
    token_hash = hash_refresh_token(
        refresh_token
    )

    # SAVE DATABASE
    # MySQL DATETIME thÆ°á»ng lÆ°u dáº¡ng naive datetime
    expires_at_db = (
        expires_at_utc.replace(
            tzinfo=None
        )
    )

    create_refresh_token_record(
        db=db,

        user_id=user_id,

        jti=jti,

        token_hash=token_hash,

        expires_at=expires_at_db
    )

    return refresh_token

# DECODE REFRESH TOKEN
def decode_refresh_token(
    token: str
) -> dict:
    """
    Decode vÃ  kiá»ƒm tra chá»¯ kÃ½ JWT Refresh Token.
    """

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[
                ALGORITHM
            ]
        )

        # TOKEN TYPE
        if (
            payload.get("type")
            != "refresh"
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token khÃ´ng há»£p lá»‡"
            )

        # REQUIRED CLAIMS
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token khÃ´ng há»£p lá»‡"
            )

        if not payload.get("jti"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token khÃ´ng há»£p lá»‡"
            )

        return payload

    except ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token Ä‘Ã£ háº¿t háº¡n"
        )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token khÃ´ng há»£p lá»‡"
        )

# VALIDATE REFRESH TOKEN
def validate_refresh_token(
    db: Session,
    *,
    token: str
):
    """
    Kiá»ƒm tra Refresh Token á»Ÿ cáº£:

    1. JWT
    2. Database
    3. jti
    4. token_hash
    5. is_revoked
    6. expires_at
    """

    # DECODE JWT
    payload = decode_refresh_token(
        token
    )

    jti = payload.get(
        "jti"
    )

    user_id = payload.get(
        "sub"
    )

    try:
        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token khÃ´ng há»£p lá»‡"
        )

    # DATABASE TOKEN
    now = datetime.utcnow()

    token_record = (
        get_active_refresh_token_by_jti(
            db,
            jti=jti,
            now=now
        )
    )

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Refresh token khÃ´ng tá»“n táº¡i, "
                "Ä‘Ã£ háº¿t háº¡n hoáº·c Ä‘Ã£ bá»‹ thu há»“i"
            )
        )

    # CHECK USER
    if (
        token_record.user_id
        != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token khÃ´ng há»£p lá»‡"
        )

    # CHECK TOKEN HASH
    incoming_hash = (
        hash_refresh_token(
            token
        )
    )

    if not hmac.compare_digest(
        incoming_hash,
        token_record.token_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token khÃ´ng há»£p lá»‡"
        )

    return (
        payload,
        token_record
    )

# ROTATE REFRESH TOKEN
def rotate_refresh_token(
    db: Session,
    *,
    token: str
) -> dict:
    """
    Refresh Token Rotation.

    Token cÅ©:
        is_revoked = True

    Sau Ä‘Ã³:
        táº¡o refresh token má»›i.

    KhÃ´ng commit táº¡i Ä‘Ã¢y.
    """

    # VALIDATE OLD TOKEN
    payload, token_record = (
        validate_refresh_token(
            db=db,
            token=token
        )
    )

    user_id = int(
        payload["sub"]
    )

    email = payload.get(
        "email"
    )

    role = payload.get(
        "role",
        "user"
    )

    # REVOKE OLD TOKEN
    revoke_refresh_token(
        db=db,

        refresh_token=token_record,

        revoked_at=datetime.utcnow()
    )

    # CREATE NEW TOKEN
    new_refresh_token = (
        create_refresh_token(
            db=db,

            user_id=user_id,

            email=email,

            role=role
        )
    )

    return {
        "userId": user_id,

        "email": email,

        "role": role,

        "refreshToken": (
            new_refresh_token
        )
    }

# REVOKE TOKEN / LOGOUT
def revoke_refresh_token_value(
    db: Session,
    *,
    token: str
):
    """
    Revoke má»™t Refresh Token.

    DÃ¹ng cho logout.

    KhÃ´ng commit táº¡i Ä‘Ã¢y.
    """

    payload, token_record = (
        validate_refresh_token(
            db=db,
            token=token
        )
    )

    revoke_refresh_token(
        db=db,

        refresh_token=token_record,

        revoked_at=datetime.utcnow()
    )

    return {
        "userId": int(
            payload["sub"]
        ),

        "jti": payload["jti"]
    }
