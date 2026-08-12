from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_model import User


def get_user_by_id(
    db: Session,
    user_id: int
) -> Optional[User]:

    return (
        db.query(User)
        .filter(User.user_id == user_id)
        .first()
    )


def get_user_by_email(
    db: Session,
    email: str
) -> Optional[User]:

    return (
        db.query(User)
        .filter(User.email == email)
        .first()
    )


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password_hash: str,
    phone_number: str | None = None,
    region: str | None = None,
    business_type: str | None = None,
    account_type: str = "personal",
    role: str = "user",
    is_verified: bool = False
) -> User:

    user = User(
        full_name=full_name,
        email=email,
        phone_number=phone_number,
        password_hash=password_hash,
        region=region,
        business_type=business_type,
        account_type=account_type,
        role=role,
        is_verified=is_verified
    )

    db.add(user)

    # Có user_id sau INSERT nhưng chưa commit
    db.flush()

    return user