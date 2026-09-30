from app.schemas.auth.auth_credential_schema import (
    RegisterRequest,
    LoginRequest,
    SendOTPRequest,
    VerifyOTPRequest,
    VerifyForgotOTPRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
    ChangePasswordRequest,
    GoogleLoginRequest,
)
from app.schemas.auth.profile_schema import UpdateProfileRequest

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

