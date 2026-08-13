from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_model import User

# GET USER BY ID
def get_user_by_id(
    db: Session,
    user_id: int
) -> Optional[User]:

    return (
        db.query(User)
        .filter(User.user_id == user_id)
        .first()
    )

# GET USER BY EMAIL
def get_user_by_email(
    db: Session,
    email: str
) -> Optional[User]:

    return (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

# CREATE USER
def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password_hash: str | None = None,
    region: str | None = None,
    account_type: str = "personal",
    store_name: str | None = None,
    business_type: str | None = None,
    google_id: str | None = None,
    apple_id: str | None = None,
    role: str = "user",
    is_verified: bool = False
) -> User:

    user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        region=region,
        account_type=account_type,
        store_name=store_name,
        business_type=business_type,
        google_id=google_id,
        apple_id=apple_id,
        role=role,
        is_verified=is_verified
    )

    db.add(user)
    db.flush()

    return user

# VERIFY USER
def verify_user(
    db: Session,
    user: User
) -> User:

    user.is_verified = True

    db.flush()

    return user

# UPDATE PASSWORD
def update_user_password(
    db: Session,
    user: User,
    password_hash: str
) -> User:

    user.password_hash = password_hash

    db.flush()

    return user

# GET USER BY GOOGLE ID
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


# LINK GOOGLE ACCOUNT
def link_google_account(
    db: Session,
    user: User,
    google_id: str
) -> User:

    user.google_id = google_id

    db.flush()

    return user