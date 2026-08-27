from datetime import datetime

from sqlalchemy.orm import Session

from app.models.otp_model import OTPCode

# CREATE OTP
def create_otp(
    db: Session,
    *,
    user_id: int | None,
    email: str,
    otp_hash: str,
    purpose: str,
    expires_at: datetime
) -> OTPCode:

    otp = OTPCode(
        user_id=user_id,
        email=email,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=expires_at,
        is_used=False,
        created_at=datetime.utcnow()
    )

    db.add(otp)
    db.flush()

    return otp

# GET LATEST OTP
def get_latest_otp(
    db: Session,
    *,
    email: str,
    purpose: str
) -> OTPCode | None:

    return (
        db.query(OTPCode)
        .filter(
            OTPCode.email == email,
            OTPCode.purpose == purpose
        )
        .order_by(
            OTPCode.created_at.desc(),
            OTPCode.otp_id.desc()
        )
        .first()
    )

# GET LATEST VALID OTP
def get_latest_valid_otp(
    db: Session,
    *,
    email: str,
    purpose: str,
    now: datetime
) -> OTPCode | None:

    return (
        db.query(OTPCode)
        .filter(
            OTPCode.email == email,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False,
            OTPCode.expires_at > now
        )
        .order_by(
            OTPCode.created_at.desc(),
            OTPCode.otp_id.desc()
        )
        .first()
    )

# MARK OTP USED
def mark_otp_used(
    db: Session,
    otp: OTPCode
) -> OTPCode:

    otp.is_used = True

    db.flush()

    return otp

# INVALIDATE OLD OTP
def invalidate_old_otps(
    db: Session,
    *,
    email: str,
    purpose: str
) -> int:

    updated_rows = (
        db.query(OTPCode)
        .filter(
            OTPCode.email == email,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False
        )
        .update(
            {
                OTPCode.is_used: True
            },
            synchronize_session=False
        )
    )

    db.flush()

    return updated_rows
