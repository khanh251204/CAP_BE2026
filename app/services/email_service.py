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
    Kiá»ƒm tra cáº¥u hÃ¬nh SMTP trÆ°á»›c khi gá»­i mail.
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
            "Thiáº¿u cáº¥u hÃ¬nh SMTP trong .env: "
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
    HÃ m gá»­i email dÃ¹ng chung.

    - SMTP Gmail
    - STARTTLS
    - Port máº·c Ä‘á»‹nh 587
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

    # Ná»™i dung text fallback
    message.set_content(
        text_content
    )

    # Ná»™i dung HTML
    if html_content:
        message.add_alternative(
            html_content,
            subtype="html"
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

            # Káº¿t ná»‘i TLS
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
                "KhÃ´ng thá»ƒ xÃ¡c thá»±c tÃ i khoáº£n "
                "SMTP gá»­i email"
            )
        )

    except smtplib.SMTPException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "KhÃ´ng thá»ƒ gá»­i email. "
                "Vui lÃ²ng thá»­ láº¡i sau."
            )
        )

    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "KhÃ´ng thá»ƒ káº¿t ná»‘i Ä‘áº¿n "
                "mÃ¡y chá»§ email"
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
    Gá»­i OTP cho:
    - verify_email
    - forgot_password
    """

    if purpose == "verify_email":

        subject = (
            "XÃ¡c thá»±c email - VoiceCashBook"
        )

        title = "XÃ¡c thá»±c email"

        description = (
            "Báº¡n Ä‘ang Ä‘Äƒng kÃ½ tÃ i khoáº£n "
            "VoiceCashBook."
        )

    elif purpose == "forgot_password":

        subject = (
            "KhÃ´i phá»¥c máº­t kháº©u - VoiceCashBook"
        )

        title = "KhÃ´i phá»¥c máº­t kháº©u"

        description = (
            "Báº¡n Ä‘Ã£ yÃªu cáº§u Ä‘áº·t láº¡i "
            "máº­t kháº©u VoiceCashBook."
        )

    else:
        raise ValueError(
            "OTP purpose khÃ´ng há»£p lá»‡"
        )

    # =====================================================
    # TEXT VERSION
    # =====================================================

    text_content = f"""
{title}

{description}

MÃ£ OTP cá»§a báº¡n lÃ :

{otp_code}

MÃ£ OTP cÃ³ hiá»‡u lá»±c trong {expire_minutes} phÃºt.

KhÃ´ng chia sáº» mÃ£ nÃ y cho báº¥t ká»³ ai.

Náº¿u báº¡n khÃ´ng thá»±c hiá»‡n yÃªu cáº§u nÃ y,
vui lÃ²ng bá» qua email.

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
                Quáº£n lÃ½ tÃ i chÃ­nh báº±ng giá»ng nÃ³i
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
            MÃ£ OTP cá»§a báº¡n:
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
            MÃ£ OTP cÃ³ hiá»‡u lá»±c trong
            <strong>{expire_minutes} phÃºt</strong>.
        </p>


        <p style="
            color: #dc2626;
            font-size: 14px;
            line-height: 1.6;
        ">
            KhÃ´ng chia sáº» mÃ£ OTP nÃ y
            cho báº¥t ká»³ ai.
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
            Náº¿u báº¡n khÃ´ng thá»±c hiá»‡n
            yÃªu cáº§u nÃ y, vui lÃ²ng bá» qua email.
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
