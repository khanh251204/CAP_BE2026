# app/schemas/auth_schema.py
# Re-export all auth schemas for 100% backward compatibility.

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    VerifyForgotOTPRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
    ChangePasswordRequest,
    GoogleLoginRequest,
    UpdateProfileRequest,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "SendOTPRequest",
    "VerifyOTPRequest",
    "VerifyForgotOTPRequest",
    "ResetPasswordRequest",
    "ForgotPasswordRequest",
    "ChangePasswordRequest",
    "GoogleLoginRequest",
    "UpdateProfileRequest",
]