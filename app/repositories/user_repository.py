from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_model import User


# ============================================================
# GET USER BY ID
# ============================================================

def get_user_by_id(
    db: Session,
    user_id: int
) -> Optional[User]:

    return (
        db.query(User)
        .filter(
            User.user_id == user_id
        )
        .first()
    )


# ============================================================
# GET USER BY EMAIL
# ============================================================

def get_user_by_email(
    db: Session,
    email: str
) -> Optional[User]:

    return (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )


# ============================================================
# GET USER BY GOOGLE ID
# ============================================================

def get_user_by_google_id(
    db: Session,
    google_id: str
) -> Optional[User]:

    return (
        db.query(User)
        .filter(
            User.google_id == google_id
        )
        .first()
    )


# ============================================================
# CREATE USER
# ============================================================

def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password_hash: str | None = None,
    phone_number: str | None = None,
    province_code: str | None = None,
    region: str | None = None,
    ward_code: str | None = None,
    ward_name: str | None = None,
    address_detail: str | None = None,
    account_type: str = "business",
    store_name: str | None = None,
    business_type: str | None = None,
    google_id: str | None = None,
    apple_id: str | None = None,
    role: str = "user",
    is_verified: bool = False
) -> User:
    """
    Tạo User mới.

    Không commit tại repository.
    Chỉ flush để lấy user_id.
    """

    user = User(
        full_name=full_name,
        email=email,
        phone_number=phone_number,
        password_hash=password_hash,

        # Location
        province_code=province_code,
        region=region,
        ward_code=ward_code,
        ward_name=ward_name,
        address_detail=address_detail,

        # Account
        account_type=account_type,

        # Business
        store_name=store_name,
        business_type=business_type,

        # OAuth
        google_id=google_id,
        apple_id=apple_id,

        # Security
        role=role,
        is_verified=is_verified
    )

    db.add(user)

    db.flush()

    return user


# ============================================================
# VERIFY USER
# ============================================================

def verify_user(
    db: Session,
    user: User
) -> User:

    user.is_verified = True

    db.flush()

    return user


# ============================================================
# UPDATE PASSWORD
# ============================================================

def update_user_password(
    db: Session,
    user: User,
    password_hash: str
) -> User:

    user.password_hash = password_hash

    db.flush()

    return user


# ============================================================
# LINK GOOGLE ACCOUNT
# ============================================================

def link_google_account(
    db: Session,
    user: User,
    google_id: str
) -> User:

    user.google_id = google_id

    db.flush()

    return user


# ============================================================
# UPDATE USER PROFILE
# ============================================================

def update_user_profile(
    user: User,
    updates: dict
) -> User:
    """
    Cập nhật profile.

    Không commit tại repository.

    Service chịu trách nhiệm:
        - validate
        - commit
        - rollback
    """

    if not updates:
        return user

    allowed_fields = {
        "full_name",
        "phone_number",
        "province_code",
        "region",
        "ward_code",
        "ward_name",
        "address_detail",
        "store_name",
        "business_type"
    }

    for field, value in updates.items():

        if field not in allowed_fields:
            continue

        setattr(
            user,
            field,
            value
        )

    return user


# ============================================================
# LOGIN ATTEMPTS / LOCK HELPERS
# ============================================================

def increment_failed_attempts(
    db: Session,
    user: User,
    max_attempts: int = 5,
    lock_duration_minutes: int = 15
) -> User:
    from datetime import datetime, timedelta
    user.failed_attempts += 1
    if user.failed_attempts >= max_attempts:
        user.lock_until = datetime.utcnow() + timedelta(
            minutes=lock_duration_minutes
        )
    db.flush()
    return user


def reset_failed_attempts(
    db: Session,
    user: User
) -> User:
    user.failed_attempts = 0
    user.lock_until = None
    db.flush()
    return user