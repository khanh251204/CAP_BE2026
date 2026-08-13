import re

from datetime import datetime

from fastapi import (
    HTTPException,
    status
)

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# CONFIG
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

# REPOSITORIES
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    verify_user,
    update_user_password
)

from app.repositories.refresh_token_repository import (
    revoke_all_user_refresh_tokens
)

# SCHEMAS
from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    VerifyOTPRequest,
    SendOTPRequest,
    RefreshTokenRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    VerifyResetOTPRequest,
    ResetPasswordRequest
)

# SERVICES
from app.services.otp_service import (
    create_otp_code,
    verify_otp_code,
    OTP_EXPIRE_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS
)

from app.services.email_service import (
    send_otp_email
)

from app.services.refresh_token_service import (
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token_value
)

# PASSWORD VALIDATION
def validate_password_strength(
    password: str
):
    """
    Password phải có:

    - >= 8 ký tự
    - chữ hoa
    - chữ thường
    - số
    """

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

# USER RESPONSE
def user_to_dict(
    user
):
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

# REGISTER=

def register_user(
    db: Session,
    data: RegisterRequest
):
    email = str(
        data.email
    ).strip().lower()
    
    # PASSWORD
    validate_password_strength(
        data.password
    )

    # CHECK EMAIL
    existing_user = (
        get_user_by_email(
            db,
            email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )
        
    # ACCOUNT DATA
    if (
        data.accountType
        == "personal"
    ):
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

    # PASSWORD HASH
    password_hash = (
        get_password_hash(
            data.password
        )
    )

    try:
        # CREATE USER
        user = create_user(
            db=db,

            full_name=(
                data.fullName.strip()
            ),

            email=email,

            password_hash=(
                password_hash
            ),

            region=(
                data.province.strip()
            ),

            account_type=(
                data.accountType
            ),

            store_name=store_name,

            business_type=(
                business_type
            ),

            role=Roles.USER,

            is_verified=False
        )

        # CREATE OTP
        otp_code = create_otp_code(
            db=db,

            user_id=user.user_id,

            email=user.email,

            purpose="verify_email"
        )
        # SEND OTP
        send_otp_email(
            to_email=user.email,

            otp_code=otp_code,

            expire_minutes=(
                OTP_EXPIRE_MINUTES
            ),

            purpose="verify_email"
        )
        
        # COMMIT
        db.commit()

        db.refresh(
            user
        )

        return {
            "success": True,

            "message": (
                "Đăng ký thành công. "
                "Mã OTP đã được gửi đến email của bạn."
            ),

            "email": user.email,

            "nextAction": (
                "verify_email"
            ),

            "otpExpiresIn": (
                OTP_EXPIRE_MINUTES
                * 60
            ),

            "resendCountdown": (
                OTP_RESEND_COOLDOWN_SECONDS
            )
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
            detail=(
                "Không thể đăng ký tài khoản. "
                "Vui lòng thử lại sau."
            )
        )

# VERIFY EMAIL OTP
def verify_email_otp(
    db: Session,
    data: VerifyOTPRequest
):
    email = str(
        data.email
    ).strip().lower()

    # USER
    user = get_user_by_email(
        db,
        email
    )

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

    try:
        # OTP
        otp = verify_otp_code(
            db=db,

            email=email,

            code=data.code,

            purpose="verify_email"
        )

        if (
            otp.user_id is not None
            and otp.user_id
            != user.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP không hợp lệ"
            )

        # VERIFY USER
        verify_user(
            db,
            user
        )
        
        # ACCESS TOKEN
        access_token = (
            create_access_token({
                "sub": str(
                    user.user_id
                ),

                "email": user.email,

                "role": user.role
            })
        )
        
        # REFRESH TOKEN
        refresh_token = (
            create_refresh_token(
                db=db,

                user_id=(
                    user.user_id
                ),

                email=user.email,

                role=user.role
            )
        )

        db.commit()

        db.refresh(
            user
        )

        return {
            "success": True,

            "message": (
                "Xác thực email thành công"
            ),

            "accessToken": (
                access_token
            ),

            "refreshToken": (
                refresh_token
            ),

            "tokenType": "bearer",

            "expiresIn": (
                ACCESS_TOKEN_EXPIRE_MINUTES
                * 60
            ),

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
            detail=(
                "Không thể xác thực email. "
                "Vui lòng thử lại sau."
            )
        )

# SEND / RESEND VERIFY EMAIL OTP
def send_verify_email_otp(
    db: Session,
    data: SendOTPRequest
):
    email = str(
        data.email
    ).strip().lower()

    user = get_user_by_email(
        db,
        email
    )

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

    try:
        otp_code = (
            create_otp_code(
                db=db,

                user_id=user.user_id,

                email=user.email,

                purpose="verify_email"
            )
        )

        send_otp_email(
            to_email=user.email,

            otp_code=otp_code,

            expire_minutes=(
                OTP_EXPIRE_MINUTES
            ),

            purpose="verify_email"
        )

        db.commit()

        return {
            "success": True,

            "message": (
                "Mã OTP mới đã được gửi "
                "đến email của bạn."
            ),

            "email": user.email,

            "otpExpiresIn": (
                OTP_EXPIRE_MINUTES
                * 60
            ),

            "resendCountdown": (
                OTP_RESEND_COOLDOWN_SECONDS
            )
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể gửi mã OTP. "
                "Vui lòng thử lại sau."
            )
        )

# FORGOT PASSWORD
def forgot_password(
    db: Session,
    data: ForgotPasswordRequest
):
    """
    Gửi OTP đặt lại mật khẩu.

    Response không tiết lộ email
    có tồn tại hay không.
    """

    email = str(
        data.email
    ).strip().lower()

    user = get_user_by_email(
        db,
        email
    )

    generic_response = {
        "success": True,

        "message": (
            "Nếu email tồn tại trong hệ thống, "
            "mã OTP sẽ được gửi đến email của bạn."
        ),

        "email": email,

        "otpExpiresIn": (
            OTP_EXPIRE_MINUTES
            * 60
        ),

        "resendCountdown": (
            OTP_RESEND_COOLDOWN_SECONDS
        )
    }

    # USER NOT ELIGIBLE
    if (
        not user
        or not user.password_hash
        or not user.is_verified
    ):
        return generic_response

    try:
        # CREATE OTP
        otp_code = create_otp_code(
            db=db,

            user_id=user.user_id,

            email=user.email,

            purpose="forgot_password"
        )

        # SEND 
        send_otp_email(
            to_email=user.email,

            otp_code=otp_code,

            expire_minutes=(
                OTP_EXPIRE_MINUTES
            ),

            purpose="forgot_password"
        )

        db.commit()

        return generic_response

    except HTTPException as exc:

        db.rollback()

        # Không để cooldown làm lộ
        # email có tồn tại hay không.
        if (
            exc.status_code
            == status.HTTP_429_TOO_MANY_REQUESTS
        ):
            return generic_response

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể xử lý yêu cầu "
                "khôi phục mật khẩu"
            )
        )

# VERIFY RESET OTP
def verify_reset_password_otp(
    db: Session,
    data: VerifyResetOTPRequest
):
    email = str(
        data.email
    ).strip().lower()

    user = get_user_by_email(
        db,
        email
    )

    if (
        not user
        or not user.password_hash
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
        # VERIFY OTP
        otp = verify_otp_code(
            db=db,

            email=email,

            code=data.code,

            purpose="forgot_password"
        )

        if (
            otp.user_id is not None
            and otp.user_id
            != user.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP không hợp lệ"
            )

        # CREATE RESET TOKEN
        reset_token = (
            create_reset_token(
                user_id=(
                    user.user_id
                ),

                email=user.email,

                password_hash=(
                    user.password_hash
                )
            )
        )

        # OTP đã được mark is_used=True
        db.commit()

        return {
            "success": True,

            "message": (
                "Xác thực OTP thành công"
            ),

            "resetToken": (
                reset_token
            ),

            "expiresIn": (
                PASSWORD_RESET_EXPIRE_MINUTES
                * 60
            ),

            "nextAction": (
                "reset_password"
            )
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
    # VALIDATE PASSWORD
    validate_password_strength(
        data.newPassword
    )

    # RESET TOKEN
    payload = decode_reset_token(
        data.resetToken
    )

    user_id = payload.get(
        "sub"
    )

    token_email = payload.get(
        "email"
    )

    token_password_fingerprint = (
        payload.get(
            "passwordFingerprint"
        )
    )

    try:
        user_id = int(
            user_id
        )

    except (
        TypeError,
        ValueError
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    # FIND USER
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

    # CHECK EMAIL
    if (
        not token_email
        or user.email.lower()
        != str(
            token_email
        ).lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reset token không hợp lệ"
        )

    # CHECK TOKEN ONE-TIME STATE
    current_password_fingerprint = (
        create_password_fingerprint(
            user.password_hash
        )
    )

    if (
        not token_password_fingerprint
        or token_password_fingerprint
        != current_password_fingerprint
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Reset token không hợp lệ "
                "hoặc đã được sử dụng"
            )
        )

    try:
        # HASH NEW PASSWORD
        new_password_hash = (
            get_password_hash(
                data.newPassword
            )
        )

        # UPDATE PASSWORD
        update_user_password(
            db=db,

            user=user,

            password_hash=(
                new_password_hash
            )
        )

        # REVOKE ALL REFRESH TOKENS
        revoke_all_user_refresh_tokens(
            db=db,

            user_id=user.user_id,

            revoked_at=(
                datetime.utcnow()
            )
        )
        
        # COMMIT
        db.commit()

        return {
            "success": True,

            "message": (
                "Đặt lại mật khẩu thành công. "
                "Vui lòng đăng nhập lại."
            ),

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
    email = str(
        data.email
    ).strip().lower()
    
    # FIND USER
    user = get_user_by_email(
        db,
        email
    )
    # PASSWORD
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
            detail=(
                "Email hoặc mật khẩu "
                "không chính xác"
            )
        )

    # VERIFIED
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tài khoản chưa được "
                "xác thực email"
            )
        )

    try:
        # ACCESS TOKEN
        access_token = (
            create_access_token({
                "sub": str(
                    user.user_id
                ),

                "email": user.email,

                "role": user.role
            })
        )

        # REFRESH TOKEN
        refresh_token = (
            create_refresh_token(
                db=db,

                user_id=user.user_id,

                email=user.email,

                role=user.role
            )
        )

        db.commit()

        return {
            "success": True,

            "accessToken": (
                access_token
            ),

            "refreshToken": (
                refresh_token
            ),

            "tokenType": "bearer",

            "expiresIn": (
                ACCESS_TOKEN_EXPIRE_MINUTES
                * 60
            ),

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
            detail="Không thể đăng nhập"
        )

# REFRESH ACCESS TOKEN
def refresh_access_token(
    db: Session,
    data: RefreshTokenRequest
):
    try:
        # ROTATE
        result = (
            rotate_refresh_token(
                db=db,

                token=(
                    data.refreshToken
                )
            )
        )

        user_id = result[
            "userId"
        ]

        # USER
        user = get_user_by_id(
            db,
            user_id
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

        # ACCESS TOKEN
        access_token = (
            create_access_token({
                "sub": str(
                    user.user_id
                ),

                "email": user.email,

                "role": user.role
            })
        )

        new_refresh_token = (
            result[
                "refreshToken"
            ]
        )
        
        # COMMIT ROTATION
        db.commit()

        return {
            "success": True,

            "accessToken": (
                access_token
            ),

            "refreshToken": (
                new_refresh_token
            ),

            "tokenType": "bearer",

            "expiresIn": (
                ACCESS_TOKEN_EXPIRE_MINUTES
                * 60
            )
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể làm mới phiên đăng nhập"
            )
        )

# LOGOUT
def logout_user(
    db: Session,
    data: LogoutRequest
):
    try:
        revoke_refresh_token_value(
            db=db,

            token=(
                data.refreshToken
            )
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
    user_id = payload.get(
        "sub"
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )

    try:
        user_id = int(
            user_id
        )

    except (
        ValueError,
        TypeError
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