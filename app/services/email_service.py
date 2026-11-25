import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.services.email_templates import (
    build_otp_email_content,
    build_new_password_email_content,
)

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "VoiceCashBook")


def validate_smtp_config():
    """Kiểm tra cấu hình SMTP trước khi gửi mail."""
    missing_configs = []
    if not SMTP_HOST:
        missing_configs.append("SMTP_HOST")
    if not SMTP_USERNAME:
        missing_configs.append("SMTP_USERNAME")
    if not SMTP_PASSWORD:
        missing_configs.append("SMTP_PASSWORD")
    if not SMTP_FROM_EMAIL:
        missing_configs.append("SMTP_FROM_EMAIL")

    if missing_configs:
        raise RuntimeError("Thiếu cấu hình SMTP trong .env: " + ", ".join(missing_configs))


def send_email(
    *,
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str | None = None,
    email_type: str = "OTHER",
    user_id: int | None = None,
    sent_by: int | None = None,
):
    """
    Hàm gửi email dùng chung qua SMTP STARTTLS và tự động ghi lịch sử vào Email_Log.
    """
    from app.services.email_management_service import record_email_log

    try:
        validate_smtp_config()
    except Exception as exc:
        record_email_log(
            to_email=to_email,
            subject=subject,
            email_type=email_type,
            status="FAILED",
            error_message=str(exc),
            text_body=text_content,
            html_body=html_content,
            user_id=user_id,
            sent_by=sent_by,
        )
        raise

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM_EMAIL))
    message["To"] = to_email
    message.set_content(text_content)

    if html_content:
        message.add_alternative(html_content, subtype="html")

    ssl_context = ssl.create_default_context()

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl_context)
            smtp.ehlo()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        record_email_log(
            to_email=to_email,
            subject=subject,
            email_type=email_type,
            status="SENT",
            text_body=text_content,
            html_body=html_content,
            user_id=user_id,
            sent_by=sent_by,
        )
    except smtplib.SMTPAuthenticationError:
        err_msg = "Không thể xác thực tài khoản SMTP gửi email"
        record_email_log(
            to_email=to_email,
            subject=subject,
            email_type=email_type,
            status="FAILED",
            error_message=err_msg,
            text_body=text_content,
            html_body=html_content,
            user_id=user_id,
            sent_by=sent_by,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )
    except smtplib.SMTPException as exc:
        err_msg = f"Không thể gửi email ({exc})"
        record_email_log(
            to_email=to_email,
            subject=subject,
            email_type=email_type,
            status="FAILED",
            error_message=err_msg,
            text_body=text_content,
            html_body=html_content,
            user_id=user_id,
            sent_by=sent_by,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể gửi email. Vui lòng thử lại sau.",
        )
    except OSError as exc:
        err_msg = f"Không thể kết nối đến máy chủ email ({exc})"
        record_email_log(
            to_email=to_email,
            subject=subject,
            email_type=email_type,
            status="FAILED",
            error_message=err_msg,
            text_body=text_content,
            html_body=html_content,
            user_id=user_id,
            sent_by=sent_by,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể kết nối đến máy chủ email",
        )


def send_otp_email(
    *,
    to_email: str,
    otp_code: str,
    expire_minutes: int,
    purpose: str
):
    """Gửi OTP cho verify_email, forgot_password hoặc unlock_account."""
    if purpose == "verify_email":
        subject = "Xác thực email - VoiceCashBook"
        title = "Xác thực email"
        description = "Bạn đang đăng ký tài khoản VoiceCashBook."
    elif purpose == "forgot_password":
        subject = "Khôi phục mật khẩu - VoiceCashBook"
        title = "Khôi phục mật khẩu"
        description = "Bạn đã yêu cầu đặt lại mật khẩu VoiceCashBook."
    elif purpose == "unlock_account":
        subject = "Mở khóa tài khoản - VoiceCashBook"
        title = "Mở khóa tài khoản"
        description = (
            "Tài khoản VoiceCashBook của bạn đã bị tạm khóa do nhập sai mật khẩu nhiều lần. "
            "Nhập mã dưới đây để mở khóa và nhận mật khẩu mới qua email."
        )
    else:
        raise ValueError("OTP purpose không hợp lệ")

    text_content, html_content = build_otp_email_content(
        title=title,
        description=description,
        otp_code=otp_code,
        expire_minutes=expire_minutes
    )

    send_email(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        email_type="OTP",
    )


def send_new_password_email(
    *,
    to_email: str,
    new_password: str,
):
    """Gửi mật khẩu mới ngẫu nhiên sau khi người dùng xác thực OTP mở khóa tài khoản thành công."""
    subject = "Mật khẩu mới sau khi mở khóa tài khoản - VoiceCashBook"
    title = "Mở khóa tài khoản thành công"
    description = (
        "Tài khoản VoiceCashBook của bạn đã được mở khóa thành công. "
        "Hệ thống đã cấp mật khẩu đăng nhập mới cho bạn như bên dưới:"
    )

    text_content, html_content = build_new_password_email_content(
        title=title,
        description=description,
        new_password=new_password,
    )

    send_email(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        email_type="PASSWORD_RESET",
    )


__all__ = [
    "validate_smtp_config",
    "send_email",
    "send_otp_email",
    "send_new_password_email",
]
