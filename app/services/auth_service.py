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
    get_user_by_id,
    verify_user
)

from app.schemas.auth_schema import (
    RegisterRequest,
    LoginRequest,
    VerifyOTPRequest,
    SendOTPRequest
)

from app.services.otp_service import (
    create_otp_code,
    verify_otp_code,
    OTP_EXPIRE_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS
)

from app.services.email_service import (
    send_otp_email
)

# PASSWORD VALIDATION
def validate_password_strength(
    password: str
):
    """
    Kiểm tra độ mạnh mật khẩu.

    Yêu cầu:
    - Ít nhất 8 ký tự
    - Ít nhất 1 chữ hoa
    - Ít nhất 1 chữ thường
    - Ít nhất 1 chữ số
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

# USER RESPONSE
def user_to_dict(user):
    """
    Convert User Model thành response cho Frontend.
    """

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
    """
    Đăng ký tài khoản.

    Flow:
    1. Validate password
    2. Check email
    3. Create User
    4. Create OTP
    5. Send OTP email
    6. Commit User + OTP
    """

    # NORMALIZE EMAIL
    email = str(
        data.email
    ).strip().lower()

    # VALIDATE PASSWORD
    validate_password_strength(
        data.password
    )

    # CHECK EMAIL EXISTS
    existing_user = get_user_by_email(
        db,
        email
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    # NORMALIZE ACCOUNT DATA
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

    # HASH PASSWORD
    password_hash = get_password_hash(
        data.password
    )

    try:
        # CREATE USER
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

            # Chưa verify OTP
            is_verified=False
        )

        # create_user sử dụng db.flush()
        # nên user.user_id đã có ở đây.

        # CREATE OTP
        otp_code = create_otp_code(
            db=db,
            user_id=user.user_id,
            email=user.email,
            purpose="verify_email"
        )

        # SEND OTP EMAIL
        send_otp_email(
            to_email=user.email,
            otp_code=otp_code,
            expire_minutes=OTP_EXPIRE_MINUTES,
            purpose="verify_email"
        )

        # COMMIT USER + OTP
        db.commit()

        db.refresh(user)

        # RESPONSE
        return {
            "success": True,

            "message": (
                "Đăng ký thành công. "
                "Mã OTP đã được gửi đến email của bạn."
            ),

            "email": user.email,

            "nextAction": "verify_email",

            "otpExpiresIn": (
                OTP_EXPIRE_MINUTES * 60
            ),

            "resendCountdown": (
                OTP_RESEND_COOLDOWN_SECONDS
            )
        }

    # DUPLICATE / DATABASE CONFLICT
    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    # HTTP ERROR
    except HTTPException:

        db.rollback()

        raise

    # UNKNOWN ERROR
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
    """
    Xác thực OTP đăng ký.

    Nếu OTP đúng:
    - OTP is_used = True
    - User is_verified = True
    - Sinh Access Token
    """

    # NORMALIZE EMAIL
    email = str(
        data.email
    ).strip().lower()

    # FIND USER
    user = get_user_by_email(
        db,
        email
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản"
        )

    # ALREADY VERIFIED
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được xác thực"
        )

    try:
        # VERIFY OTP
        otp = verify_otp_code(
            db=db,
            email=email,
            code=data.code,
            purpose="verify_email"
        )

        # SECURITY CHECK
        if (
            otp.user_id is not None
            and otp.user_id != user.user_id
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

        # CREATE ACCESS TOKEN
        access_token = create_access_token({
            "sub": str(
                user.user_id
            ),
            "email": user.email,
            "role": user.role
        })

        # COMMIT OTP + USER
        db.commit()

        db.refresh(user)

        # RESPONSE
        return {
            "success": True,

            "message": (
                "Xác thực email thành công"
            ),

            "accessToken": access_token,

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
    """
    Gửi lại OTP xác thực email.

    create_otp_code() sẽ xử lý:
    - Cooldown
    - Invalidate OTP cũ
    - Generate OTP mới
    - Hash OTP
    - Lưu OTP_Code
    """

    # NORMALIZE EMAIL
    email = str(
        data.email
    ).strip().lower()

    # FIND USER
    user = get_user_by_email(
        db,
        email
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản"
        )

    # ALREADY VERIFIED
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được xác thực"
        )

    try:

        # CREATE NEW OTP
        otp_code = create_otp_code(
            db=db,
            user_id=user.user_id,
            email=user.email,
            purpose="verify_email"
        )

        # SEND EMAIL
        send_otp_email(
            to_email=user.email,
            otp_code=otp_code,
            expire_minutes=OTP_EXPIRE_MINUTES,
            purpose="verify_email"
        )

        # COMMIT
        db.commit()

        # RESPONSE
        return {
            "success": True,

            "message": (
                "Mã OTP mới đã được gửi "
                "đến email của bạn."
            ),

            "email": user.email,

            "otpExpiresIn": (
                OTP_EXPIRE_MINUTES * 60
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

# LOGIN
def login_user(
    db: Session,
    data: LoginRequest
):
    """
    Login bằng email + password.

    Chỉ cho đăng nhập nếu:
    - Email tồn tại
    - Password đúng
    - Email đã verify
    """
    # NORMALIZE EMAIL
    email = str(
        data.email
    ).strip().lower()

    # FIND USER
    user = get_user_by_email(
        db,
        email
    )

    # VERIFY PASSWORD

    # Không tiết lộ:
    # - email có tồn tại hay không
    # - password sai hay không

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
    
    # EMAIL NOT VERIFIED
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tài khoản chưa được "
                "xác thực email"
            )
        )
    
    # CREATE ACCESS TOKEN
    access_token = create_access_token({
        "sub": str(
            user.user_id
        ),
        "email": user.email,
        "role": user.role
    })
    
    # RESPONSE
    return {
        "success": True,

        "accessToken": access_token,

        "expiresIn": (
            ACCESS_TOKEN_EXPIRE_MINUTES
            * 60
        ),

        "user": user_to_dict(
            user
        )
    }

# CURRENT USER
def get_current_user(
    db: Session,
    payload: dict
):
    """
    Lấy thông tin user từ JWT Access Token.
    """

    # USER ID FROM TOKEN
    user_id = payload.get(
        "sub"
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )
    
    # CONVERT USER ID
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

    # FIND USER
    user = get_user_by_id(
        db,
        user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại"
        )

    # RESPONSE
    return {
        "success": True,

        "user": user_to_dict(
            user
        )
    }