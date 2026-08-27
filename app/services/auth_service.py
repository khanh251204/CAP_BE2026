import re

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers.notification_controller import NotificationController

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
            detail="Máº­t kháº©u pháº£i cÃ³ Ã­t nháº¥t 8 kÃ½ tá»±"
        )

    if not re.search(
        r"[A-Z]",
        password
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Máº­t kháº©u pháº£i cÃ³ Ã­t nháº¥t 1 chá»¯ hoa"
        )

    if not re.search(
        r"[a-z]",
        password
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Máº­t kháº©u pháº£i cÃ³ Ã­t nháº¥t 1 chá»¯ thÆ°á»ng"
        )

    if not re.search(
        r"\d",
        password
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Máº­t kháº©u pháº£i cÃ³ Ã­t nháº¥t 1 chá»¯ sá»‘"
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

# SESSION

def create_session(
    db: Session,
    user
) -> dict:

    # ACCESS TOKEN
    access_token = create_access_token({
        "sub": str(
            user.user_id
        ),
        "email": user.email,
        "role": user.role
    })

    # REFRESH TOKEN
    refresh_token = create_refresh_token(
        db=db,
        user_id=user.user_id,
        email=user.email,
        role=user.role
    )

    # SESSION RESPONSE
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

    # CHECK EMAIL
    if get_user_by_email(
        db,
        email
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email Ä‘Ã£ Ä‘Æ°á»£c Ä‘Äƒng kÃ½"
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

        # CREATE USER
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

        # SEND OTP
        otp_info = send_otp(
            db,
            user=user,
            purpose=VERIFY_EMAIL
        )

        # COMMIT
        db.commit()

        db.refresh(
            user
        )

        # NOTIFICATION
        NotificationController.create_notification({
            "userId": str(user.user_id),
            "title": "ÄÄƒng kÃ½ thÃ nh cÃ´ng ðŸŽ‰",
            "description": "ChÃ o má»«ng báº¡n Ä‘áº¿n vá»›i VoiceCashBook!",
            "icon": "check",
            "iconColor": "#FFFFFF",
            "borderColor": "#20D66B",
            "notificationType": "register",
            "isRead": False
        })


        # RESPONSE
        # KhÃ´ng tráº£ message
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
            detail="Email Ä‘Ã£ Ä‘Æ°á»£c Ä‘Äƒng kÃ½"
        )

    except HTTPException:

        db.rollback()

        raise

    except Exception as e:

        db.rollback()

        print(
            "âŒ REGISTER ERROR:",
            str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="KhÃ´ng thá»ƒ Ä‘Äƒng kÃ½ tÃ i khoáº£n"
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
                detail="KhÃ´ng tÃ¬m tháº¥y tÃ i khoáº£n"
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email Ä‘Ã£ Ä‘Æ°á»£c xÃ¡c thá»±c"
            )

    # FORGOT PASSWORD
    if data.purpose == FORGOT_PASSWORD:

        # KhÃ´ng lÃ m lá»™ email cÃ³ tá»“n táº¡i hay khÃ´ng
        response = {
            "success": True,
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


        # FORGOT PASSWORD
        if data.purpose == FORGOT_PASSWORD:

            return {
                "success": True,
                **otp_info
            }


        # VERIFY EMAIL
        return {
            "success": True,
            "email": user.email,
            **otp_info
        }

    except HTTPException as exc:

        db.rollback()

        # KhÃ´ng lÃ m lá»™ email khi forgot password
        if (
            data.purpose == FORGOT_PASSWORD
            and exc.status_code
            == status.HTTP_429_TOO_MANY_REQUESTS
        ):
            return {
                "success": True,
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
            detail="KhÃ´ng thá»ƒ gá»­i mÃ£ OTP"
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

    # USER NOT FOUND
    if not user:

        if data.purpose == FORGOT_PASSWORD:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MÃ£ OTP khÃ´ng há»£p lá»‡ hoáº·c Ä‘Ã£ háº¿t háº¡n"
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KhÃ´ng tÃ¬m tháº¥y tÃ i khoáº£n"
        )

    # VERIFY EMAIL
    if data.purpose == VERIFY_EMAIL:

        if user.is_verified:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email Ä‘Ã£ Ä‘Æ°á»£c xÃ¡c thá»±c"
            )

    # FORGOT PASSWORD
    if data.purpose == FORGOT_PASSWORD:

        if (
            not user.password_hash
            or not user.is_verified
        ):

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MÃ£ OTP khÃ´ng há»£p lá»‡ hoáº·c Ä‘Ã£ háº¿t háº¡n"
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

            # Sau khi verify email
            # cáº¥p cáº£ Access + Refresh Token
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


        # FORGOT PASSWORD
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
            detail="KhÃ´ng thá»ƒ xÃ¡c thá»±c OTP"
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
            detail="Reset token khÃ´ng há»£p lá»‡"
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
            detail="Reset token khÃ´ng há»£p lá»‡"
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
            detail="Reset token khÃ´ng há»£p lá»‡"
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
                "Reset token khÃ´ng há»£p lá»‡ "
                "hoáº·c Ä‘Ã£ Ä‘Æ°á»£c sá»­ dá»¥ng"
            )
        )

    try:


        # UPDATE PASSWORD
        update_user_password(
            db=db,
            user=user,
            password_hash=get_password_hash(
                data.newPassword
            )
        )


        # REVOKE ALL REFRESH TOKENS
        revoke_all_user_refresh_tokens(
            db=db,
            user_id=user.user_id,
            revoked_at=datetime.utcnow()
        )

        db.commit()

        # RESPONSE
        return {
            "success": True,
            "nextAction": "login"
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="KhÃ´ng thá»ƒ Ä‘áº·t láº¡i máº­t kháº©u"
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

    # CHECK ACCOUNT
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
            detail="Email hoáº·c máº­t kháº©u khÃ´ng chÃ­nh xÃ¡c"
        )

    # CHECK EMAIL
    if not user.is_verified:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TÃ i khoáº£n chÆ°a Ä‘Æ°á»£c xÃ¡c thá»±c email"
        )

    try:


        # CREATE SESSION
        session = create_session(
            db,
            user
        )

        db.commit()

        db.refresh(
            user
        )


        # NOTIFICATION
        NotificationController.create_notification({
            "userId": str(user.user_id),
            "title": "ÄÄƒng nháº­p thÃ nh cÃ´ng ðŸ‘‹",
            "description": (
                f"ChÃ o má»«ng {user.full_name} "
                "quay trá»Ÿ láº¡i VoiceCashBook!"
            ),
            "icon": "check",
            "iconColor": "#FFFFFF",
            "borderColor": "#20D66B",
            "notificationType": "login",
            "isRead": False
        })


        # RESPONSE
        # KhÃ´ng cÃ³ message
        #
        # Váº«n tráº£:
        # - accessToken
        # - refreshToken
        # - expiresIn
        # - tokenType
        # - user
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
            "âŒ Login error:",
            e
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="KhÃ´ng thá»ƒ Ä‘Äƒng nháº­p"
        )

# GOOGLE LOGIN
def google_login(
    db: Session,
    data: GoogleLoginRequest
):
    # GOOGLE TOKEN
    if data.idToken:

        token_val = data.idToken

    elif data.code and data.redirectUri:

        token_val = exchange_code_for_id_token(
            code=data.code,
            code_verifier=data.codeVerifier,
            redirect_uri=data.redirectUri
        )

    else:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Thiáº¿u idToken hoáº·c thiáº¿u thÃ´ng tin "
                "Authorization Code "
                "(code, redirectUri)"
            )
        )

    # VERIFY GOOGLE TOKEN
    google_data = verify_google_id_token(
        token_val
    )

    google_id = google_data[
        "googleId"
    ]

    email = normalize_email(
        google_data["email"]
    )

    try:


        # 1. FIND BY GOOGLE ID
        user = get_user_by_google_id(
            db,
            google_id
        )


        # 2. GOOGLE ACCOUNT DOES NOT EXIST
        if not user:

            existing_user = get_user_by_email(
                db,
                email
            )

            if existing_user:
                # Email exists but Google not linked
                if not existing_user.google_id:

                    user = link_google_account(
                        db=db,
                        user=existing_user,
                        google_id=google_id
                    )

                # Email linked to another Google account
                elif (
                    existing_user.google_id
                    != google_id
                ):

                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Email nÃ y Ä‘Ã£ Ä‘Æ°á»£c liÃªn káº¿t "
                            "vá»›i má»™t tÃ i khoáº£n Google khÃ¡c."
                        )
                    )

                else:

                    user = existing_user

            # 3. CREATE NEW GOOGLE USER
            else:

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


        # 4. CREATE SESSION
        # Quan trá»ng:
        # Google Login cÅ©ng cáº¥p:
        # Access Token + Refresh Token

        session = create_session(
            db,
            user
        )

        db.commit()

        db.refresh(
            user
        )


        # RESPONSE
        # KhÃ´ng cÃ³ message


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
                "KhÃ´ng thá»ƒ liÃªn káº¿t "
                "tÃ i khoáº£n Google."
            )
        )

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "KhÃ´ng thá»ƒ Ä‘Äƒng nháº­p "
                "báº±ng Google."
            )
        )


# REFRESH TOKEN
def refresh_access_token(
    db: Session,
    token: str
):
    try:


        # ROTATE REFRESH TOKEN
        result = rotate_refresh_token(
            db=db,
            token=token
        )


        # FIND USER
        user = get_user_by_id(
            db,
            result["userId"]
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="NgÆ°á»i dÃ¹ng khÃ´ng tá»“n táº¡i"
            )


        # CHECK VERIFIED
        if not user.is_verified:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="TÃ i khoáº£n chÆ°a Ä‘Æ°á»£c xÃ¡c thá»±c"
            )


        # CREATE NEW ACCESS TOKEN
        access = create_access_session(
            user
        )

        db.commit()


        # RESPONSE
        #
        # Access Token má»›i
        # Refresh Token má»›i


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
            detail="KhÃ´ng thá»ƒ lÃ m má»›i phiÃªn Ä‘Äƒng nháº­p"
        )


# LOGOUT
def logout_user(
    db: Session,
    token: str
):
    try:


        # REVOKE REFRESH TOKEN
        revoke_refresh_token_value(
            db=db,
            token=token
        )

        db.commit()

        return {"success": True}

    except HTTPException:

        db.rollback()

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="KhÃ´ng thá»ƒ Ä‘Äƒng xuáº¥t"
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
            detail="Token khÃ´ng há»£p lá»‡"
        )

    user = get_user_by_id(
        db,
        user_id
    )

    if not user:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="NgÆ°á»i dÃ¹ng khÃ´ng tá»“n táº¡i"
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
                detail="KhÃ´ng tÃ¬m tháº¥y ngÆ°á»i dÃ¹ng"
            )

        request_data = data.model_dump(
            exclude_unset=True
        )


        # ACCOUNT TYPE
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
                    detail="TÃªn cá»­a hÃ ng/doanh nghiá»‡p lÃ  báº¯t buá»™c"
                )

            if (
                not business_field
                or not business_field.strip()
            ):

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="LÄ©nh vá»±c kinh doanh lÃ  báº¯t buá»™c"
                )


        # PERSONAL ACCOUNT
        if account_type == "personal":

            store_name = None
            business_field = None

        updates = {}


        # FULL NAME
        if "fullName" in request_data:

            updates["full_name"] = (
                request_data["fullName"].strip()
            )


        # PHONE
        if "phoneNumber" in request_data:

            phone_number = request_data[
                "phoneNumber"
            ]

            updates["phone_number"] = (
                phone_number.strip()
                if phone_number
                else None
            )


        # PROVINCE CODE
        if "provinceCode" in request_data:

            prov_code_val = request_data[
                "provinceCode"
            ]

            updates["province_code"] = (
                prov_code_val.strip()
                if prov_code_val
                else None
            )


        # PROVINCE
        if "province" in request_data:

            prov_val = request_data[
                "province"
            ]

            updates["region"] = (
                prov_val.strip()
                if prov_val
                else None
            )


        # WARD CODE
        if "wardCode" in request_data:

            ward_code_val = request_data[
                "wardCode"
            ]

            updates["ward_code"] = (
                ward_code_val.strip()
                if ward_code_val
                else None
            )


        # WARD
        if "ward" in request_data:

            ward_val = request_data[
                "ward"
            ]

            updates["ward_name"] = (
                ward_val.strip()
                if ward_val
                else None
            )


        # ADDRESS
        if "addressDetail" in request_data:

            addr_detail_val = request_data[
                "addressDetail"
            ]

            updates["address_detail"] = (
                addr_detail_val.strip()
                if addr_detail_val
                else None
            )


        # CLEAR WARD WHEN PROVINCE CHANGES
        if "provinceCode" in request_data:

            new_prov_code = request_data[
                "provinceCode"
            ]

            current_prov_code = (
                user.province_code
            )

            if (
                new_prov_code
                != current_prov_code
            ):

                if "wardCode" not in request_data:

                    updates["ward_code"] = None
                    updates["ward_name"] = None


        # ACCOUNT TYPE
        if "accountType" in request_data:

            updates["account_type"] = (
                account_type
            )


        # BUSINESS DATA
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


        # PERSONAL DATA
        else:

            updates["store_name"] = None
            updates["business_type"] = None

        # UPDATE DATABASE
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
            detail="KhÃ´ng thá»ƒ cáº­p nháº­t thÃ´ng tin"
        )
