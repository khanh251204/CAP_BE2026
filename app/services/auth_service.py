import re

from fastapi import (
    HTTPException,
    status
)

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.configs.jwt import (
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

from app.configs.roles import Roles

from app.configs.security import (
    get_password_hash,
    verify_password
)

from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id
)

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest
)

# HELPER
def validate_password_strength(
    password: str
):
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 8 ký tự"
        )

    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 1 chữ hoa"
        )

    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 1 chữ thường"
        )

    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 1 chữ số"
        )


def user_to_dict(user):
    return {
        "userId": user.user_id,
        "fullName": user.full_name,
        "email": user.email,

        "province": user.region,

        "accountType": user.account_type,

        "storeName": user.store_name,

        "businessField": user.business_type,

        "role": user.role,

        "isVerified": bool(
            user.is_verified
        )
    }

# REGISTER
def register_user(
    db: Session,
    data: RegisterRequest
):
    email = str(
        data.email
    ).strip().lower()

    # =========================
    # PASSWORD
    # =========================

    validate_password_strength(
        data.password
    )

    # =========================
    # CHECK EMAIL
    # =========================

    existing_user = get_user_by_email(
        db,
        email
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    # =========================
    # NORMALIZE ACCOUNT
    # =========================

    if data.accountType == "personal":

        store_name = None
        business_type = None

    else:

        store_name = (
            data.storeName.strip()
            if data.storeName
            else None
        )

        business_type = (
            data.businessField.strip()
            if data.businessField
            else None
        )

    # =========================
    # HASH PASSWORD
    # =========================

    password_hash = get_password_hash(
        data.password
    )

    try:

        user = create_user(
            db=db,

            full_name=data.fullName.strip(),

            email=email,

            password_hash=password_hash,

            region=data.province.strip(),

            account_type=data.accountType,

            store_name=store_name,

            business_type=business_type,

            role=Roles.USER,

            # Phải OTP trước
            is_verified=False
        )

        db.commit()

        db.refresh(user)

        return {
            "success": True,

            "message": (
                "Đăng ký thành công. "
                "Vui lòng xác thực email."
            ),

            "email": user.email,

            "nextAction": "verify_email"
        }

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    except HTTPException:

        db.rollback()

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng ký tài khoản"
        )

# LOGIN
def login_user(
    db: Session,
    data: LoginRequest
):
    email = str(
        data.email
    ).strip().lower()

    user = get_user_by_email(
        db,
        email
    )

    # Không tiết lộ email có tồn tại hay không
    if (
        not user
        or not user.password_hash
        or not verify_password(
            data.password,
            user.password_hash
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác"
        )

    # Chưa verify OTP
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được xác thực email"
        )

    access_token = create_access_token({
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role
    })

    return {
        "success": True,

        "accessToken": access_token,

        "expiresIn": (
            ACCESS_TOKEN_EXPIRE_MINUTES * 60
        ),

        "user": user_to_dict(user)
    }

# CURRENT USER

def get_current_user(
    db: Session,
    payload: dict
):
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

    try:
        user_id = int(user_id)

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

    user = get_user_by_id(
        db,
        user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại"
        )

    return {
        "success": True,
        "user": user_to_dict(user)
    }