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
    password_hash: str,
    region: str,
    account_type: str,
    store_name: str | None = None,
    business_type: str | None = None,
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
        role=role,
        is_verified=is_verified
    )

    db.add(user)

    # Có user_id nhưng chưa commit
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