from datetime import datetime

from sqlalchemy.orm import Session

from app.models.refresh_token_model import RefreshToken


# ============================================================
# CREATE REFRESH TOKEN
# ============================================================
def create_refresh_token(
    db: Session,
    *,
    user_id: int,
    jti: str,
    token_hash: str,
    expires_at: datetime
) -> RefreshToken:
    """
    Lưu refresh token vào database.

    Database chỉ lưu:
    - user_id
    - jti
    - token_hash
    - expires_at

    Không lưu refresh token plaintext.

    Repository không commit.
    """

    refresh_token = RefreshToken(
        user_id=user_id,
        jti=jti,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False
    )

    db.add(refresh_token)
    db.flush()

    return refresh_token


# ============================================================
# GET REFRESH TOKEN BY JTI
# ============================================================
def get_refresh_token_by_jti(
    db: Session,
    jti: str
) -> RefreshToken | None:
    """
    Tìm refresh token theo JWT ID.
    """

    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.jti == jti
        )
        .first()
    )


# ============================================================
# GET ACTIVE REFRESH TOKEN
# ============================================================
def get_active_refresh_token_by_jti(
    db: Session,
    *,
    jti: str,
    now: datetime
) -> RefreshToken | None:
    """
    Lấy refresh token còn hiệu lực:

    - Đúng jti
    - Chưa bị revoke
    - Chưa hết hạn
    """

    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.jti == jti,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now
        )
        .first()
    )


# ============================================================
# REVOKE REFRESH TOKEN
# ============================================================
def revoke_refresh_token(
    db: Session,
    refresh_token: RefreshToken,
    revoked_at: datetime
) -> RefreshToken:
    """
    Vô hiệu hóa một refresh token.

    Dùng cho:
    - Logout
    - Refresh token rotation
    """

    refresh_token.is_revoked = True
    refresh_token.revoked_at = revoked_at

    db.flush()

    return refresh_token


# ============================================================
# REVOKE ALL USER REFRESH TOKENS
# ============================================================
def revoke_all_user_refresh_tokens(
    db: Session,
    *,
    user_id: int,
    revoked_at: datetime
) -> int:
    """
    Revoke toàn bộ refresh token đang hoạt động của user.

    Dùng cho:
    - Logout all devices
    - Đổi password
    - Security incident
    """

    updated_rows = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False)
        )
        .update(
            {
                RefreshToken.is_revoked: True,
                RefreshToken.revoked_at: revoked_at
            },
            synchronize_session=False
        )
    )

    db.flush()

    return updated_rows