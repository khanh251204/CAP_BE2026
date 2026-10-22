import os
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import jwt, JWTError, ExpiredSignatureError
from sqlalchemy.orm import Session

from app.configs.jwt import SECRET_KEY, ALGORITHM
from app.configs.settings import settings
from app.repositories.refresh_token_repository import (
    create_refresh_token as create_refresh_token_record,
    get_active_refresh_token_by_jti,
    revoke_refresh_token,
    delete_expired_and_revoked_tokens
)

load_dotenv()

REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


def hash_refresh_token(token: str) -> str:
    """Hash refresh token bằng SHA256. Database chỉ lưu hash."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(
    db: Session,
    *,
    user_id: int,
    email: str,
    role: str
) -> str:
    """Tạo JWT Refresh Token và lưu hash vào DB. Không commit tại đây."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at_utc = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "jti": jti,
        "type": "refresh",
        "exp": expires_at_utc
    }

    refresh_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    token_hash = hash_refresh_token(refresh_token)
    expires_at_db = expires_at_utc.replace(tzinfo=None)

    create_refresh_token_record(
        db=db,
        user_id=user_id,
        jti=jti,
        token_hash=token_hash,
        expires_at=expires_at_db
    )

    return refresh_token


def decode_refresh_token(token: str) -> dict:
    """Decode và kiểm tra chữ ký JWT Refresh Token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token không hợp lệ"
            )

        if not payload.get("sub") or not payload.get("jti"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token không hợp lệ"
            )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token đã hết hạn"
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ"
        )


def validate_refresh_token(db: Session, *, token: str):
    """Kiểm tra Refresh Token ở JWT, Database, hash, trạng thái revoked."""
    payload = decode_refresh_token(token)
    jti = payload.get("jti")
    raw_sub = payload.get("sub")

    try:
        user_id = int(raw_sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ"
        )

    now = datetime.utcnow()
    token_record = get_active_refresh_token_by_jti(db, jti=jti, now=now)

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không tồn tại, đã hết hạn hoặc đã bị thu hồi"
        )

    if token_record.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ"
        )

    incoming_hash = hash_refresh_token(token)
    if not hmac.compare_digest(incoming_hash, token_record.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ"
        )

    return payload, token_record


def rotate_refresh_token(db: Session, *, token: str) -> dict:
    """Refresh Token Rotation: thu hồi token cũ và phát hành token mới."""
    payload, token_record = validate_refresh_token(db=db, token=token)

    user_id = int(payload["sub"])
    email = payload.get("email")
    role = payload.get("role", "user")

    revoke_refresh_token(db=db, refresh_token=token_record, revoked_at=datetime.utcnow())
    new_refresh_token = create_refresh_token(db=db, user_id=user_id, email=email, role=role)

    return {
        "userId": user_id,
        "email": email,
        "role": role,
        "refreshToken": new_refresh_token
    }


def revoke_refresh_token_value(db: Session, *, token: str):
    """Revoke một Refresh Token khi logout. Không commit tại đây."""
    payload, token_record = validate_refresh_token(db=db, token=token)
    revoke_refresh_token(db=db, refresh_token=token_record, revoked_at=datetime.utcnow())

    return {
        "userId": int(payload["sub"]),
        "jti": payload["jti"]
    }


def purge_expired_refresh_tokens(db: Session) -> int:
    """
    Xóa cứng toàn bộ refresh token đã hết hạn hoặc đã thu hồi khỏi DB.
    Trả về số lượng bản ghi đã được dọn dẹp.
    """
    now = datetime.utcnow()
    return delete_expired_and_revoked_tokens(db=db, now=now)


__all__ = [
    "hash_refresh_token",
    "create_refresh_token",
    "decode_refresh_token",
    "validate_refresh_token",
    "rotate_refresh_token",
    "revoke_refresh_token_value",
    "purge_expired_refresh_tokens",
]