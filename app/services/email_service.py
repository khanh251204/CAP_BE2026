import os
import smtplib
import ssl

from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv
from fastapi import HTTPException, status


# =========================================================
# LOAD ENV
# =========================================================

load_dotenv()


SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com"
)

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME"
)

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD"
)

SMTP_FROM_EMAIL = os.getenv(
    "SMTP_FROM_EMAIL"
)

SMTP_FROM_NAME = os.getenv(
    "SMTP_FROM_NAME",
    "VoiceCashBook"
)


# =========================================================
# VALIDATE SMTP CONFIG
# =========================================================

def validate_smtp_config():
    """
    Kiểm tra cấu hình SMTP trước khi gửi mail.
    """

    missing_configs = []

    if not SMTP_HOST:
        missing_configs.append(
            "SMTP_HOST"
        )

    if not SMTP_USERNAME:
        missing_configs.append(
            "SMTP_USERNAME"
        )

    if not SMTP_PASSWORD:
        missing_configs.append(
            "SMTP_PASSWORD"
        )

    if not SMTP_FROM_EMAIL:
        missing_configs.append(
            "SMTP_FROM_EMAIL"
        )

    if missing_configs:
        raise RuntimeError(
            "Thiếu cấu hình SMTP trong .env: "
            + ", ".join(
                missing_configs
            )
        )


# =========================================================
# SEND EMAIL
# =========================================================

def send_email(
    *,
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str | None = None
):
    """
    Hàm gửi email dùng chung.

    - SMTP Gmail
    - STARTTLS
    - Port mặc định 587
    """

    validate_smtp_config()

    message = EmailMessage()

    message["Subject"] = subject

    message["From"] = formataddr(
        (
            SMTP_FROM_NAME,
            SMTP_FROM_EMAIL
        )
    )

    message["To"] = to_email

    # Nội dung text fallback
    message.set_content(
        text_content,
        charset="utf-8"
    )

    # Nội dung HTML
    if html_content:
        message.add_alternative(
            html_content,
            subtype="html",
            charset="utf-8"
        )

    ssl_context = (
        ssl.create_default_context()
    )

    try:
        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=15
        ) as smtp:

            # Kết nối TLS
            smtp.ehlo()

            smtp.starttls(
                context=ssl_context
            )

            smtp.ehlo()

            # Login SMTP
            smtp.login(
                SMTP_USERNAME,
                SMTP_PASSWORD
            )

            # Send
            smtp.send_message(
                message
            )

    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể xác thực tài khoản "
                "SMTP gửi email"
            )
        )

    except smtplib.SMTPException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể gửi email. "
                "Vui lòng thử lại sau."
            )
        )

    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Không thể kết nối đến "
                "máy chủ email"
            )
        )


# =========================================================
# SEND OTP EMAIL
# =========================================================

def send_otp_email(
    *,
    to_email: str,
    otp_code: str,
    expire_minutes: int,
    purpose: str
):
    """
    Gửi OTP cho:
    - verify_email
    - forgot_password
    """

    if purpose == "verify_email":

        subject = (
            "Xác thực email - VoiceCashBook"
        )

        title = "Xác thực email"

        description = (
            "Bạn đang đăng ký tài khoản "
            "VoiceCashBook."
        )

    elif purpose == "forgot_password":

        subject = (
            "Khôi phục mật khẩu - VoiceCashBook"
        )

        title = "Khôi phục mật khẩu"

        description = (
            "Bạn đã yêu cầu đặt lại "
            "mật khẩu VoiceCashBook."
        )

    else:
        raise ValueError(
            "OTP purpose không hợp lệ"
        )

    # =====================================================
    # TEXT VERSION
    # =====================================================

    text_content = f"""
{title}

{description}

Mã OTP của bạn là:

{otp_code}

Mã OTP có hiệu lực trong {expire_minutes} phút.

Không chia sẻ mã này cho bất kỳ ai.

Nếu bạn không thực hiện yêu cầu này,
vui lòng bỏ qua email.

VoiceCashBook
""".strip()

    # =====================================================
    # HTML VERSION
    # =====================================================

    html_content = f"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>{title} - VoiceCashBook</title>
</head>

<body style="
    margin: 0;
    padding: 0;
    background-color: #f5f7f6;
    font-family: Arial, Helvetica, sans-serif;
">

    <div style="
        max-width: 520px;
        margin: 40px auto;
        background-color: #ffffff;
        border-radius: 16px;
        padding: 36px;
        box-shadow:
            0 4px 20px rgba(0, 0, 0, 0.06);
    ">

        <div style="
            text-align: center;
            margin-bottom: 24px;
        ">

            <div style="
                font-size: 28px;
                font-weight: 700;
                color: #111827;
            ">
                VoiceCashBook
            </div>

            <div style="
                margin-top: 6px;
                font-size: 14px;
                color: #6b7280;
            ">
                Quản lý tài chính bằng giọng nói
            </div>

        </div>


        <h2 style="
            color: #111827;
            font-size: 22px;
            margin-bottom: 12px;
        ">
            {title}
        </h2>


        <p style="
            color: #4b5563;
            font-size: 15px;
            line-height: 1.6;
        ">
            {description}
        </p>


        <p style="
            color: #4b5563;
            font-size: 15px;
        ">
            Mã OTP của bạn:
        </p>


        <div style="
            margin: 24px 0;
            padding: 18px;

            background-color: #ecfdf3;

            border-radius: 12px;

            text-align: center;

            font-size: 32px;
            font-weight: 700;

            letter-spacing: 8px;

            color: #16a34a;
        ">
            {otp_code}
        </div>


        <p style="
            color: #4b5563;
            font-size: 14px;
            line-height: 1.6;
        ">
            Mã OTP có hiệu lực trong
            <strong>{expire_minutes} phút</strong>.
        </p>


        <p style="
            color: #dc2626;
            font-size: 14px;
            line-height: 1.6;
        ">
            Không chia sẻ mã OTP này
            cho bất kỳ ai.
        </p>


        <hr style="
            border: none;
            border-top: 1px solid #e5e7eb;
            margin: 28px 0;
        ">


        <p style="
            color: #9ca3af;
            font-size: 12px;
            line-height: 1.6;
        ">
            Nếu bạn không thực hiện
            yêu cầu này, vui lòng bỏ qua email.
        </p>

    </div>

</body>
</html>
"""

    send_email(
        to_email=to_email,
        subject=subject,
        text_content=text_content,
        html_content=html_content
    )