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
    role: str = "OWNER",
    role_id: int | None = None,
    is_verified: bool = False
) -> User:
    if not role_id:
        from app.models.role_permission_model import Role
        target_role = db.query(Role).filter(Role.role_name == role.upper()).first()
        if not target_role:
            target_role = db.query(Role).filter(Role.role_name == "OWNER").first()
        if target_role:
            role_id = target_role.role_id

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
        role_id=role_id,
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


# UPDATE USER PROFILE
def update_user_profile(
    db: Session,
    user: User,
    *,
    full_name: str | None = None,
    phone_number: str | None = None,
    region: str | None = None,
    account_type: str | None = None,
    store_name: str | None = None,
    business_type: str | None = None,
    province_code: str | None = None,
    ward_code: str | None = None,
    ward_name: str | None = None,
    address_detail: str | None = None
) -> User:
    if full_name is not None:
        user.full_name = full_name.strip()
    if phone_number is not None:
        user.phone_number = phone_number.strip() if phone_number else None
    if region is not None:
        user.region = region.strip() if region else None
    if account_type is not None:
        user.account_type = account_type.strip()
    if store_name is not None:
        clean_name = store_name.strip() if store_name else None
        if clean_name:
            if user.store_rel:
                user.store_rel.store_name = clean_name
            else:
                from app.models.store_model import Store
                new_store = Store(user_id=user.user_id, store_name=clean_name, business_type=user.business_type)
                db.add(new_store)
                db.flush()
                user.store_id = new_store.store_id
    if business_type is not None:
        user.business_type = business_type.strip().upper() if business_type else None
        if user.store_rel and user.business_type:
            user.store_rel.business_type = user.business_type
    if province_code is not None:
        user.province_code = province_code.strip() if province_code else None
    if ward_code is not None:
        user.ward_code = ward_code.strip() if ward_code else None
    if ward_name is not None:
        user.ward_name = ward_name.strip() if ward_name else None
    if address_detail is not None:
        clean_addr = address_detail.strip() if address_detail else None
        if user.store_rel:
            user.store_rel.address_detail = clean_addr

    db.flush()
    return user