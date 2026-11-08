import re
import logging
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.controllers.notification_controller import NotificationController
from app.configs.roles import Roles
from app.configs.security import get_password_hash
from app.repositories.user_repository import create_user, get_user_by_email
from app.schemas.auth_schema import RegisterRequest
from app.services.otp_service import send_otp, VERIFY_EMAIL


def normalize_email(email) -> str:
    return str(email).strip().lower()


def validate_password_strength(password: str):
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
        "phone": user.phone_number,
        "phoneNumber": user.phone_number,
        "province": user.region,
        "region": user.region,
        "accountType": user.account_type,
        "storeName": user.store_name,
        "businessField": user.business_type,
        "businessType": user.business_type,
        "provinceCode": user.province_code,
        "wardCode": user.ward_code,
        "wardName": user.ward_name,
        "addressDetail": user.address_detail,
        "role": user.role,
        "isVerified": bool(user.is_verified)
    }


def register_user(db: Session, data: RegisterRequest):
    email = normalize_email(data.email)
    validate_password_strength(data.password)

    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký"
        )

    store_name = None
    business_type = "RESELLER"

    if data.accountType == "business":
        store_name = data.storeName.strip() if data.storeName else None
        business_type = data.businessField.strip() if data.businessField else "RESELLER"
    elif data.businessField:
        business_type = data.businessField.strip()

    try:
        user = create_user(
            db=db,
            full_name=data.fullName.strip(),
            email=email,
            password_hash=get_password_hash(data.password),
            region=data.province.strip(),
            account_type=data.accountType,
            store_name=store_name,
            business_type=business_type,
            role=Roles.USER,
            is_verified=False
        )

        otp_info = send_otp(db, user=user, purpose=VERIFY_EMAIL)
        db.commit()
        db.refresh(user)

        # User đã commit: lỗi gửi thông báo chào mừng không được biến thành lỗi đăng ký
        try:
            NotificationController.create_notification({
                "userId": str(user.user_id),
                "title": "Đăng ký thành công 🎉",
                "description": "Chào mừng bạn đến với VoiceCashBook!",
                "icon": "check",
                "iconColor": "#FFFFFF",
                "borderColor": "#20D66B",
                "notificationType": "register",
                "isRead": False
            })
        except Exception as e:
            logger.warning(f"Không tạo được thông báo chào mừng cho user {user.user_id}: {e}")

        return {
            "success": True,
            "message": "Đăng ký thành công. Mã OTP đã được gửi đến email.",
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
        logger.error(f"Register error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đăng ký tài khoản"
        )
