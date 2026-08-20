import re

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.configs.jwt import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    create_password_fingerprint,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    PASSWORD_RESET_EXPIRE_MINUTES
)

from app.configs.roles import Roles

from app.configs.security import (
    get_password_hash,
    verify_password
)

from app.repositories.user_repository import (
    get_user_by_id,
    update_user_profile
)

from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_google_id,
    verify_user,
    update_user_password
)

from app.repositories.refresh_token_repository import (
    revoke_all_user_refresh_tokens
)

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    GoogleLoginRequest
)

from app.services.google_auth_service import (
    verify_google_id_token
)

from app.services.otp_service import (
    send_otp,
    verify_otp,
    OTP_EXPIRE_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS,
    VERIFY_EMAIL,
    FORGOT_PASSWORD
)

from app.services.refresh_token_service import (
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token_value
)


# HELPERS
def normalize_email(
    email
) -> str:
    return str(
        email
    ).strip().lower()


def validate_password_strength(
    password: str
):
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 8 ký tự"
        )

    if not re.search(
        r"[A-Z]",
        password
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 1 chữ hoa"
        )

    if not re.search(
        r"[a-z]",
        password
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 1 chữ thường"
        )

    if not re.search(
        r"\d",
        password
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 1 chữ số"
        )


def user_to_dict(user):
    return {
        "userId": user.user_id,
        "fullName": user.full_name,
        "email": user.email,
        "phoneNumber": user.phone_number,

        "provinceCode": user.province_code,
        "province": user.region,

        "wardCode": user.ward_code,
        "ward": user.ward_name,
        "addressDetail": user.address_detail,

        "accountType": user.account_type,
        "storeName": user.store_name,
        "businessField": user.business_type,

        "role": user.role,
        "isVerified": bool(user.is_verified),

        "createdAt": (
            user.created_at.isoformat()
            if user.created_at
            else None
        )
    }

def create_session(
    db: Session,
    user
) -> dict:
    access_token = create_access_token({
        "sub": str(
            user.user_id
        ),
        "email": user.email,
        "role": user.role
    })

    refresh_token = create_refresh_token(
        db=db,
        user_id=user.user_id,
        email=user.email,
        role=user.role
    )

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "bearer",
        "expiresIn": (
            ACCESS_TOKEN_EXPIRE_MINUTES
            * 60
        )
    }


def create_access_session(
    user
) -> dict:
    access_token = create_access_token({
        "sub": str(
            user.user_id
        ),
        "email": user.email,
        "role": user.role
    })

    return {
        "accessToken": access_token,
        "tokenType": "bearer",
        "expiresIn": (
            ACCESS_TOKEN_EXPIRE_MINUTES
            * 60
        )
    }


# REGISTER
def register_user(
    db: Session,
    data: RegisterRequest
):
    email = normalize_email(
        data.email
    )

    validate_password_strength(
        data.password
    )

    if get_user_by_email(
        db,
        email
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    store_name = None
    business_type = None

    if data.accountType == "business":
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

    try:
        user = create_user(
            db=db,
            full_name=data.fullName.strip(),
            email=email,
            password_hash=get_password_hash(
                data.password
            ),
            region=data.province.strip(),
            account_type=data.accountType,
            store_name=store_name,
            business_type=business_type,
            role=Roles.USER,
            is_verified=False
        )

        otp_info = send_otp(
            db,
            user=user,
            purpose=VERIFY_EMAIL
        )

        db.commit()

        db.refresh(
            user
        )

        return {
            "success": True,
            "message": (
                "Đăng ký thành công. "
                "Mã OTP đã được gửi đến email."
            ),
            "email": user.email,
            "nextAction": "verify_email",
            **otp_info
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


# SEND OTP
def send_auth_otp(
    db: Session,
    data: SendOTPRequest
):
    email = normalize_email(
        data.email
    )

    user = get_user_by_email(
        db,
        email
    )

    # VERIFY EMAIL
    if data.purpose == VERIFY_EMAIL:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy tài khoản"
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email đã được xác thực"
            )

    # FORGOT PASSWORD
    if data.purpose == FORGOT_PASSWORD:
        response = {
            "success": True,
            "message": (
                "Nếu email tồn tại trong hệ thống, "
                "mã OTP sẽ được gửi đến email."
            ),
            "otpExpiresIn": (
                OTP_EXPIRE_MINUTES
                * 60
            ),
            "resendCountdown": (
                OTP_RESEND_COOLDOWN_SECONDS
            )
        }

        if (
            not user
            or not user.password_hash
            or not user.is_verified
        ):
            return response

    try:
        otp_info = send_otp(
            db,
            user=user,
            purpose=data.purpose
        )

        db.commit()

        if data.purpose == FORGOT_PASSWORD:
            return {
                "success": True,
                "message": (
                    "Nếu email tồn tại trong hệ thống, "
                    "mã OTP sẽ được gửi đến email."
                ),
                **otp_info
            }

        return {
            "success": True,
            "message": "Mã OTP đã được gửi",
            "email": user.email,
            **otp_info
        }

    except HTTPException as exc:
        db.rollback()

        # Không làm lộ email khi forgot password
        if (
            data.purpose == FORGOT_PASSWORD
            and exc.status_code
            == status.HTTP_429_TOO_MANY_REQUESTS
        ):
            return {
                "success": True,
                "message": (
                    "Nếu email tồn tại trong hệ thống, "
                    "mã OTP sẽ được gửi đến email."
                ),
                "otpExpiresIn": (
                    OTP_EXPIRE_MINUTES
                    * 60
                ),
                "resendCountdown": (
                    OTP_RESEND_COOLDOWN_SECONDS
                )
            }

        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể gửi mã OTP"
        )


# VERIFY OTP
def verify_auth_otp(
    db: Session,
    data: VerifyOTPRequest
):
    email = normalize_email(
        data.email
    )

    user = get_user_by_email(
        db,
        email
    )

    if not user:
        if data.purpose == FORGOT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP không hợp lệ hoặc đã hết hạn"
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản"
        )

    if data.purpose == VERIFY_EMAIL:
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email đã được xác thực"
            )

    if data.purpose == FORGOT_PASSWORD:
        if (
            not user.password_hash
            or not user.is_verified
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP không hợp lệ hoặc đã hết hạn"
            )

    try:
        verify_otp(
            db,
            user=user,
            code=data.code,
            purpose=data.purpose
        )

        # VERIFY EMAIL
        if data.purpose == VERIFY_EMAIL:
            verify_user(
                db,
                user
            )

            session = create_session(
                db,
                user
            )

            db.commit()

            db.refresh(
                user
            )

            return {
                "success": True,
                "message": "Xác thực email thành công",
                **session,
                "user": user_to_dict(
                    user
                )
            }

        # FORGOT PASSWORD
        reset_token = create_reset_token(
            user_id=user.user_id,
            email=user.email,
            password_hash=user.password_hash
        )

        db.commit()

        return {
            "success": True,
            "message": "Xác thực OTP thành công",
            "resetToken": reset_token,
            "expiresIn": (
                PASSWORD_RESET_EXPIRE_MINUTES
                * 60
            ),
            "nextAction": "reset_password"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xác thực OTP"
        )


# RESET PASSWORD
def reset_password(
    db: Session,
    data: ResetPasswordRequest
):
    validate_password_strength(
        data.newPassword
    )

    payload = decode_reset_token(
        data.resetToken
    )

    try:
        user_id = int(
            payload["sub"]
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    user = get_user_by_id(
        db,
        user_id
    )

    if (
        not user
        or not user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    token_email = normalize_email(
        payload.get(
            "email",
            ""
        )
    )

    if token_email != normalize_email(
        user.email
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    fingerprint = create_password_fingerprint(
        user.password_hash
    )

    if (
        payload.get(
            "passwordFingerprint"
        )
        != fingerprint
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Reset token không hợp lệ "
                "hoặc đã được sử dụng"
            )
        )

    try:
        update_user_password(
            db=db,
            user=user,
            password_hash=get_password_hash(
                data.newPassword
            )
        )

        revoke_all_user_refresh_tokens(
            db=db,
            user_id=user.user_id,
            revoked_at=datetime.utcnow()
        )

        db.commit()

        return {
            "success": True,
            "message": "Đặt lại mật khẩu thành công",
            "nextAction": "login"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đặt lại mật khẩu"
        )


# LOGIN
def login_user(
    db: Session,
    data: LoginRequest
):
    email = normalize_email(
        data.email
    )

    user = get_user_by_email(
        db,
        email
    )

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

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được xác thực email"
        )

    try:
        session = create_session(
            db,
            user
        )

        db.commit()

        return {
            "success": True,
            **session,
            "user": user_to_dict(
                user
            )
        }

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng nhập"
        )


# GOOGLE LOGIN
def google_login(
    db: Session,
    data: GoogleLoginRequest
):
    google_data = verify_google_id_token(
        data.idToken
    )

    google_id = google_data[
        "googleId"
    ]

    email = normalize_email(
        google_data["email"]
    )

    try:
        user = get_user_by_google_id(
            db,
            google_id
        )

        if not user:
            existing_user = get_user_by_email(
                db,
                email
            )

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Email đã tồn tại. "
                        "Vui lòng đăng nhập bằng mật khẩu."
                    )
                )

            user = create_user(
                db=db,
                full_name=google_data[
                    "fullName"
                ],
                email=email,
                password_hash=None,
                region=None,
                account_type="personal",
                store_name=None,
                business_type=None,
                google_id=google_id,
                role=Roles.USER,
                is_verified=True
            )

        session = create_session(
            db,
            user
        )

        db.commit()

        db.refresh(
            user
        )

        return {
            "success": True,
            **session,
            "user": user_to_dict(
                user
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tài khoản Google đã tồn tại"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng nhập bằng Google"
        )


# REFRESH TOKEN
def refresh_access_token(
    db: Session,
    token: str
):
    try:
        result = rotate_refresh_token(
            db=db,
            token=token
        )

        user = get_user_by_id(
            db,
            result["userId"]
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Người dùng không tồn tại"
            )

        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản chưa được xác thực"
            )

        access = create_access_session(
            user
        )

        db.commit()

        return {
            "success": True,
            **access,
            "refreshToken": result[
                "refreshToken"
            ]
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể làm mới phiên đăng nhập"
        )

# LOGOUT
def logout_user(
    db: Session,
    token: str
):
    try:
        revoke_refresh_token_value(
            db=db,
            token=token
        )

        db.commit()

        return {
            "success": True,
            "message": "Đăng xuất thành công"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng xuất"
        )

# CURRENT USER
def get_current_user(
    db: Session,
    payload: dict
):
    try:
        user_id = int(
            payload.get("sub")
        )

    except (
        TypeError,
        ValueError
    ):
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
        "user": user_to_dict(
            user
        )
    }

# UPDATE PROFILE
def update_profile(
    db: Session,
    payload: dict,
    data
):
    try:
        user_id = int(
            payload.get("sub")
        )

        user = get_user_by_id(
            db=db,
            user_id=user_id
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )

        request_data = data.model_dump(
            exclude_unset=True
        )

        account_type = request_data.get(
            "accountType",
            user.account_type
        )

        store_name = request_data.get(
            "storeName",
            user.store_name
        )

        business_field = request_data.get(
            "businessField",
            user.business_type
        )

        # BUSINESS ACCOUNT
        if account_type == "business":

            if (
                not store_name
                or not store_name.strip()
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Tên cửa hàng/doanh nghiệp là bắt buộc"
                )

            if (
                not business_field
                or not business_field.strip()
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Lĩnh vực kinh doanh là bắt buộc"
                )

        # PERSONAL ACCOUNT
        if account_type == "personal":
            store_name = None
            business_field = None

        updates = {}

        if "fullName" in request_data:
            updates["full_name"] = (
                request_data["fullName"].strip()
            )

        if "phoneNumber" in request_data:
            phone_number = request_data[
                "phoneNumber"
            ]

            updates["phone_number"] = (
                phone_number.strip()
                if phone_number
                else None
            )

        if "provinceCode" in request_data:
            prov_code_val = request_data["provinceCode"]
            updates["province_code"] = prov_code_val.strip() if prov_code_val else None

        if "province" in request_data:
            prov_val = request_data["province"]
            updates["region"] = prov_val.strip() if prov_val else None

        if "wardCode" in request_data:
            ward_code_val = request_data["wardCode"]
            updates["ward_code"] = ward_code_val.strip() if ward_code_val else None

        if "ward" in request_data:
            ward_val = request_data["ward"]
            updates["ward_name"] = ward_val.strip() if ward_val else None

        if "addressDetail" in request_data:
            addr_detail_val = request_data["addressDetail"]
            updates["address_detail"] = addr_detail_val.strip() if addr_detail_val else None

        # Clear ward if province changed and new ward is not provided in request
        if "provinceCode" in request_data:
            new_prov_code = request_data["provinceCode"]
            current_prov_code = user.province_code
            if new_prov_code != current_prov_code:
                if "wardCode" not in request_data:
                    updates["ward_code"] = None
                    updates["ward_name"] = None

        if "accountType" in request_data:
            updates["account_type"] = (
                account_type
            )

        if account_type == "business":

            if (
                "storeName" in request_data
                or "accountType" in request_data
            ):
                updates["store_name"] = (
                    store_name.strip()
                )

            if (
                "businessField" in request_data
                or "accountType" in request_data
            ):
                updates["business_type"] = (
                    business_field.strip()
                )

        else:
            updates["store_name"] = None
            updates["business_type"] = None

        update_user_profile(
            user=user,
            updates=updates
        )

        db.commit()

        db.refresh(
            user
        )

        return {
            "success": True,
            "message": "Cập nhật thông tin thành công",
            "user": user_to_dict(
                user
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật thông tin"
        )