import re

from datetime import datetime

from fastapi import (
    HTTPException,
    status
)

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
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_google_id,
    link_google_account,
    update_user_password,
    update_user_profile,
    verify_user,
    increment_failed_attempts,
    reset_failed_attempts
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
    GoogleLoginRequest,
    UpdateProfileRequest
)

from app.services.google_auth_service import (
    verify_google_id_token,
    exchange_code_for_id_token
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


# ============================================================
# HELPERS
# ============================================================

def normalize_email(email) -> str:
    return str(email).strip().lower()


# ============================================================
# PASSWORD VALIDATION
# ============================================================

def validate_password_strength(
    password: str
):
    """
    Password phải có:
        - >= 8 ký tự
        - ít nhất 1 chữ hoa
        - ít nhất 1 chữ thường
        - ít nhất 1 chữ số
    """

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


# ============================================================
# USER SERIALIZER
# ============================================================

def user_to_dict(user) -> dict:
    return {
        "userId": user.user_id,

        "fullName": user.full_name,

        "email": user.email,

        "phoneNumber": user.phone_number,

        # LOCATION
        "provinceCode": getattr(
            user,
            "province_code",
            None
        ),

        "province": user.region,

        "wardCode": getattr(
            user,
            "ward_code",
            None
        ),

        "ward": getattr(
            user,
            "ward_name",
            None
        ),

        "addressDetail": getattr(
            user,
            "address_detail",
            None
        ),

        # ACCOUNT
        "accountType": user.account_type,

        # BUSINESS
        "storeName": getattr(
            user,
            "store_name",
            None
        ),

        "businessField": user.business_type,

        # ROLE
        "role": user.role,

        # STATUS
        "isVerified": bool(
            user.is_verified
        ),

        # TIMESTAMP
        "createdAt": (
            user.created_at.isoformat()
            if user.created_at
            else None
        )
    }


# ============================================================
# CREATE SESSION
# ============================================================

def create_session(
    db: Session,
    user
) -> dict:

    access_token = create_access_token(
        {
            "sub": str(user.user_id),
            "email": user.email,
            "role": user.role
        }
    )

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
            ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    }


# ============================================================
# ACCESS TOKEN ONLY
# ============================================================

def create_access_session(
    user
) -> dict:

    access_token = create_access_token(
        {
            "sub": str(user.user_id),
            "email": user.email,
            "role": user.role
        }
    )

    return {
        "accessToken": access_token,
        "tokenType": "bearer",
        "expiresIn": (
            ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    }


# ============================================================
# REGISTER
# ============================================================

def register_user(
    db: Session,
    data: RegisterRequest
):
    """
    Đăng ký tài khoản Tiểu thương.

    accountType luôn là:
        business
    """

    email = normalize_email(
        data.email
    )

    validate_password_strength(
        data.password
    )

    # --------------------------------------------------------
    # CHECK EMAIL
    # --------------------------------------------------------

    existing_user = get_user_by_email(
        db,
        email
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    # --------------------------------------------------------
    # FORCE BUSINESS
    # --------------------------------------------------------

    if data.accountType != "business":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Hiện tại hệ thống chỉ hỗ trợ "
                "tài khoản Tiểu thương"
            )
        )

    # --------------------------------------------------------
    # CLEAN DATA
    # --------------------------------------------------------

    full_name = data.fullName.strip()
    phone_number = (
        data.phoneNumber.strip()
        if data.phoneNumber
        else None
    )

    province_code = (
        data.provinceCode.strip()
        if data.provinceCode
        else None
    )

    province = data.province.strip()

    ward_code = (
        data.wardCode.strip()
        if data.wardCode
        else None
    )

    ward = (
        data.ward.strip()
        if data.ward
        else None
    )

    address_detail = (
        data.addressDetail.strip()
        if data.addressDetail
        else None
    )

    store_name = data.storeName.strip()

    business_type = data.businessField.strip()

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Họ tên không được để trống"
        )

    if not province:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tỉnh / thành phố không được để trống"
        )

    if not store_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tên cửa hàng không được để trống"
        )

    if not business_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lĩnh vực kinh doanh không được để trống"
        )

    try:

        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

        user = create_user(
            db=db,

            full_name=full_name,

            email=email,

            password_hash=get_password_hash(
                data.password
            ),

            phone_number=phone_number,

            province_code=province_code,

            region=province,

            ward_code=ward_code,

            ward_name=ward,

            address_detail=address_detail,

            account_type="business",

            store_name=store_name,

            business_type=business_type,

            role=Roles.USER,

            is_verified=False
        )

        # ----------------------------------------------------
        # SEND OTP
        # ----------------------------------------------------

        otp_info = send_otp(
            db,
            user=user,
            purpose=VERIFY_EMAIL
        )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

        db.refresh(user)

        return {
            "success": True,

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

    except Exception as e:

        db.rollback()

        print(
            "REGISTER ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng ký tài khoản"
        )


# ============================================================
# SEND OTP
# ============================================================

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

    # ========================================================
    # VERIFY EMAIL
    # ========================================================

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

    # ========================================================
    # FORGOT PASSWORD
    # ========================================================

    if data.purpose == FORGOT_PASSWORD:

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email chưa đăng ký tài khoản"
            )

        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tài khoản này đăng nhập bằng Google, không thể đặt lại mật khẩu bằng email."
            )

        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tài khoản chưa được xác thực email. Vui lòng xác thực email trước khi đặt lại mật khẩu."
            )

    # ========================================================
    # SEND OTP
    # ========================================================

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
                **otp_info
            }

        return {
            "success": True,
            "email": user.email,
            **otp_info
        }

    except HTTPException as exc:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        print(
            "SEND OTP ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể gửi mã OTP"
        )


# ============================================================
# VERIFY OTP
# ============================================================

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

    # ========================================================
    # USER NOT FOUND
    # ========================================================

    if not user:

        if data.purpose == FORGOT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Mã OTP không hợp lệ "
                    "hoặc đã hết hạn"
                )
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản"
        )

    # ========================================================
    # VERIFY EMAIL
    # ========================================================

    if data.purpose == VERIFY_EMAIL:

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email đã được xác thực"
            )

    # ========================================================
    # FORGOT PASSWORD
    # ========================================================

    if data.purpose == FORGOT_PASSWORD:

        if (
            not user.password_hash
            or not user.is_verified
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Mã OTP không hợp lệ "
                    "hoặc đã hết hạn"
                )
            )

    try:

        # ----------------------------------------------------
        # VERIFY OTP
        # ----------------------------------------------------

        verify_otp(
            db,
            user=user,
            code=data.code,
            purpose=data.purpose
        )

        # ====================================================
        # VERIFY EMAIL
        # ====================================================

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

            db.refresh(user)

            return {
                "success": True,

                **session,

                "user": user_to_dict(
                    user
                )
            }

        # ====================================================
        # FORGOT PASSWORD
        # ====================================================

        reset_token = create_reset_token(
            user_id=user.user_id,

            email=user.email,

            password_hash=user.password_hash
        )

        db.commit()

        return {
            "success": True,

            "resetToken": reset_token,

            "expiresIn": (
                PASSWORD_RESET_EXPIRE_MINUTES * 60
            ),

            "nextAction": "reset_password"
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        print(
            "VERIFY OTP ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xác thực OTP"
        )


# ============================================================
# RESET PASSWORD
# ============================================================

def reset_password(
    db: Session,
    data: ResetPasswordRequest
):

    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    validate_password_strength(
        data.newPassword
    )

    # --------------------------------------------------------
    # DECODE RESET TOKEN
    # --------------------------------------------------------

    try:

        payload = decode_reset_token(
            data.resetToken
        )

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    # --------------------------------------------------------
    # USER ID
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # GET USER
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CHECK EMAIL
    # --------------------------------------------------------

    token_email = normalize_email(
        payload.get(
            "email",
            ""
        )
    )

    user_email = normalize_email(
        user.email
    )

    if token_email != user_email:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    # --------------------------------------------------------
    # CHECK PASSWORD FINGERPRINT
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # UPDATE PASSWORD
        # ----------------------------------------------------

        update_user_password(
            db=db,

            user=user,

            password_hash=get_password_hash(
                data.newPassword
            )
        )

        # ----------------------------------------------------
        # REVOKE ALL REFRESH TOKENS
        # ----------------------------------------------------

        revoke_all_user_refresh_tokens(
            db=db,

            user_id=user.user_id,

            revoked_at=datetime.utcnow()
        )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

        return {
            "success": True,
            "nextAction": "login"
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        print(
            "RESET PASSWORD ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đặt lại mật khẩu"
        )


# ============================================================
# LOGIN
# ============================================================

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

    # --------------------------------------------------------
    # USER NOT FOUND
    # --------------------------------------------------------

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Email không tồn tại trong hệ thống"
            )
        )

    # --------------------------------------------------------
    # GOOGLE ONLY
    # --------------------------------------------------------

    if not user.password_hash:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Tài khoản này được đăng nhập bằng Google"
            )
        )

    # --------------------------------------------------------
    # CHECK LOCK STATUS
    # --------------------------------------------------------

    if user.lock_until and datetime.utcnow() < user.lock_until:
        remaining_seconds = int((user.lock_until - datetime.utcnow()).total_seconds())
        remaining_minutes = max(1, int(remaining_seconds / 60))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Tài khoản đang bị khóa. "
                f"Vui lòng quay lại sau {remaining_minutes} phút."
            )
        )
    elif user.lock_until:
        # Lock expired, reset failed attempts
        reset_failed_attempts(db, user)
        db.commit()

    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    if not verify_password(
        data.password,
        user.password_hash
    ):
        increment_failed_attempts(db, user, max_attempts=5, lock_duration_minutes=15)
        db.commit()

        if user.failed_attempts >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Tài khoản đã bị khóa do nhập sai mật khẩu quá 5 lần. "
                    "Vui lòng thử lại sau 15 phút."
                )
            )
        else:
            remaining = 5 - user.failed_attempts
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Mật khẩu không chính xác. Bạn còn {remaining} lần thử."
            )

    # --------------------------------------------------------
    # VERIFIED
    # --------------------------------------------------------

    if not user.is_verified:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tài khoản chưa được xác thực email"
            )
        )

    try:
        # Reset lock state on successful login
        reset_failed_attempts(db, user)

        session = create_session(
            db,
            user
        )

        db.commit()

        db.refresh(user)

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

    except Exception as e:

        db.rollback()

        print(
            "LOGIN ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng nhập"
        )


# ============================================================
# GOOGLE LOGIN
# ============================================================

def google_login(
    db: Session,
    data: GoogleLoginRequest
):

    # ========================================================
    # GET GOOGLE TOKEN
    # ========================================================

    if data.idToken:

        token_value = data.idToken

    elif (
        data.code
        and data.redirectUri
    ):

        token_value = exchange_code_for_id_token(
            code=data.code,
            code_verifier=data.codeVerifier,
            redirect_uri=data.redirectUri
        )

    else:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Thiếu idToken hoặc thiếu thông tin "
                "Authorization Code "
                "(code, redirectUri)"
            )
        )

    # ========================================================
    # VERIFY GOOGLE TOKEN
    # ========================================================

    google_data = verify_google_id_token(
        token_value
    )

    google_id = google_data[
        "googleId"
    ]

    email = normalize_email(
        google_data["email"]
    )

    try:

        # ====================================================
        # FIND GOOGLE USER
        # ====================================================

        user = get_user_by_google_id(
            db,
            google_id
        )

        # ====================================================
        # GOOGLE USER NOT FOUND
        # ====================================================

        if not user:

            existing_user = get_user_by_email(
                db,
                email
            )

            # ------------------------------------------------
            # EMAIL EXISTS
            # ------------------------------------------------

            if existing_user:

                if not existing_user.google_id:

                    user = link_google_account(
                        db=db,

                        user=existing_user,

                        google_id=google_id
                    )

                elif (
                    existing_user.google_id
                    != google_id
                ):

                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Email này đã được liên kết "
                            "với một tài khoản Google khác."
                        )
                    )

                else:

                    user = existing_user

            # ------------------------------------------------
            # CREATE GOOGLE USER
            # ------------------------------------------------

            else:

                user = create_user(
                    db=db,

                    full_name=(
                        google_data["fullName"]
                    ),

                    email=email,

                    password_hash=None,

                    account_type="business",

                    store_name=None,

                    business_type=None,

                    google_id=google_id,

                    role=Roles.USER,

                    is_verified=True
                )

        # ====================================================
        # CREATE SESSION
        # ====================================================

        session = create_session(
            db,
            user
        )

        db.commit()

        db.refresh(user)

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
            detail=(
                "Không thể liên kết tài khoản Google."
            )
        )

    except Exception as e:

        db.rollback()

        print(
            "GOOGLE LOGIN ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể đăng nhập bằng Google."
            )
        )


# ============================================================
# REFRESH ACCESS TOKEN
# ============================================================

def refresh_access_token(
    db: Session,
    token: str
):

    try:

        # ----------------------------------------------------
        # ROTATE REFRESH TOKEN
        # ----------------------------------------------------

        result = rotate_refresh_token(
            db=db,
            token=token
        )

        # ----------------------------------------------------
        # GET USER
        # ----------------------------------------------------

        user = get_user_by_id(
            db,
            result["userId"]
        )

        if not user:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Người dùng không tồn tại"
            )

        # ----------------------------------------------------
        # VERIFIED
        # ----------------------------------------------------

        if not user.is_verified:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Tài khoản chưa được "
                    "xác thực"
                )
            )

        # ----------------------------------------------------
        # NEW ACCESS TOKEN
        # ----------------------------------------------------

        access = create_access_session(
            user
        )

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

        return {
            "success": True,

            **access,

            "refreshToken": (
                result["refreshToken"]
            )
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        print(
            "REFRESH TOKEN ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể làm mới phiên "
                "đăng nhập"
            )
        )


# ============================================================
# LOGOUT
# ============================================================

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
            "success": True
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        print(
            "LOGOUT ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng xuất"
        )


# ============================================================
# CURRENT USER
# ============================================================

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


# ============================================================
# UPDATE PROFILE
# ============================================================

def update_profile(
    db: Session,
    payload: dict,
    data: UpdateProfileRequest
):

    try:

        # ====================================================
        # USER ID
        # ====================================================

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

        # ====================================================
        # FIND USER
        # ====================================================

        user = get_user_by_id(
            db=db,
            user_id=user_id
        )

        if not user:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )

        # ====================================================
        # REQUEST DATA
        # ====================================================

        request_data = data.model_dump(
            exclude_unset=True
        )

        updates = {}

        # ====================================================
        # FULL NAME
        # ====================================================

        if "fullName" in request_data:

            value = request_data[
                "fullName"
            ]

            if value is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Họ tên không được để trống"
                )

            value = value.strip()

            if not value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Họ tên không được để trống"
                )

            updates["full_name"] = value

        # ====================================================
        # PHONE
        # ====================================================

        if "phoneNumber" in request_data:

            value = request_data[
                "phoneNumber"
            ]

            updates["phone_number"] = (
                value.strip()
                if value
                else None
            )

        # ====================================================
        # PROVINCE CODE
        # ====================================================

        if "provinceCode" in request_data:

            value = request_data[
                "provinceCode"
            ]

            updates["province_code"] = (
                value.strip()
                if value
                else None
            )

        # ====================================================
        # PROVINCE
        # ====================================================

        if "province" in request_data:

            value = request_data[
                "province"
            ]

            updates["region"] = (
                value.strip()
                if value
                else None
            )

        # ====================================================
        # WARD CODE
        # ====================================================

        if "wardCode" in request_data:

            value = request_data[
                "wardCode"
            ]

            updates["ward_code"] = (
                value.strip()
                if value
                else None
            )

        # ====================================================
        # WARD
        # ====================================================

        if "ward" in request_data:

            value = request_data[
                "ward"
            ]

            updates["ward_name"] = (
                value.strip()
                if value
                else None
            )

        # ====================================================
        # ADDRESS
        # ====================================================

        if "addressDetail" in request_data:

            value = request_data[
                "addressDetail"
            ]

            updates["address_detail"] = (
                value.strip()
                if value
                else None
            )

        # ====================================================
        # CLEAR WARD WHEN PROVINCE CHANGES
        # ====================================================

        if "provinceCode" in request_data:

            new_province_code = (
                request_data[
                    "provinceCode"
                ]
            )

            current_province_code = getattr(
                user,
                "province_code",
                None
            )

            if (
                new_province_code
                != current_province_code
                and "wardCode"
                not in request_data
            ):

                updates["ward_code"] = None
                updates["ward_name"] = None

        # ====================================================
        # STORE NAME
        # ====================================================

        if "storeName" in request_data:

            value = request_data[
                "storeName"
            ]

            if (
                not value
                or not value.strip()
            ):

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Tên cửa hàng là bắt buộc"
                )

            updates["store_name"] = (
                value.strip()
            )

        # ====================================================
        # BUSINESS FIELD
        # ====================================================

        if "businessField" in request_data:

            value = request_data[
                "businessField"
            ]

            if (
                not value
                or not value.strip()
            ):

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Lĩnh vực kinh doanh "
                        "là bắt buộc"
                    )
                )

            updates["business_type"] = (
                value.strip()
            )

        # ====================================================
        # ACCOUNT TYPE CANNOT CHANGE
        # ====================================================

        # Không đọc accountType từ request.
        #
        # Schema đã extra="forbid"
        # nên nếu frontend gửi:
        #
        # {
        #   "accountType": "personal"
        # }
        #
        # => FastAPI tự reject 422.

        # ====================================================
        # UPDATE
        # ====================================================

        update_user_profile(
            user=user,
            updates=updates
        )

        # ====================================================
        # COMMIT
        # ====================================================

        db.commit()

        db.refresh(user)

        return {
            "success": True,

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
            detail="Không thể cập nhật thông tin"
        )

    except Exception as e:

        db.rollback()

        print(
            "UPDATE PROFILE ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật thông tin"
        )