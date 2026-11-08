def build_otp_email_content(
    title: str,
    description: str,
    otp_code: str,
    expire_minutes: int
) -> tuple[str, str]:
    """Tạo text_content và html_content cho email OTP."""
    text_content = f"""{title}

{description}

Mã OTP của bạn là:

{otp_code}

Mã OTP có hiệu lực trong {expire_minutes} phút.

Không chia sẻ mã này cho bất kỳ ai.

Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.

VoiceCashBook
""".strip()

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f7f6; font-family: Arial, Helvetica, sans-serif;">
    <div style="max-width: 520px; margin: 40px auto; background-color: #ffffff; border-radius: 16px; padding: 36px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);">
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="font-size: 28px; font-weight: 700; color: #111827;">VoiceCashBook</div>
            <div style="margin-top: 6px; font-size: 14px; color: #6b7280;">Quản lý tài chính bằng giọng nói</div>
        </div>
        <h2 style="color: #111827; font-size: 22px; margin-bottom: 12px;">{title}</h2>
        <p style="color: #4b5563; font-size: 15px; line-height: 1.6;">{description}</p>
        <p style="color: #4b5563; font-size: 15px;">Mã OTP của bạn:</p>
        <div style="margin: 24px 0; padding: 18px; background-color: #ecfdf3; border-radius: 12px; text-align: center; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #16a34a;">
            {otp_code}
        </div>
        <p style="color: #4b5563; font-size: 14px; line-height: 1.6;">
            Mã OTP có hiệu lực trong <strong>{expire_minutes} phút</strong>.
        </p>
        <p style="color: #dc2626; font-size: 14px; line-height: 1.6;">
            Không chia sẻ mã OTP này cho bất kỳ ai.
        </p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 28px 0;">
        <p style="color: #9ca3af; font-size: 12px; line-height: 1.6;">
            Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.
        </p>
    </div>
</body>
</html>
"""
    return text_content, html_content
