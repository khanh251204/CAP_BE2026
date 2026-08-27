from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator
)

from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    refreshToken: str | None = None

# ============================================================
# CONSTANTS
# ============================================================

OTP_PURPOSES = (
    "verify_email",
    "forgot_password"
)


# ============================================================
# REGISTER
# ============================================================

class RegisterRequest(BaseModel):
    """
    Request đăng ký tài khoản.

    Hiện tại hệ thống chỉ hỗ trợ:
        accountType = business
        => Tiểu thương

    Không cho phép gửi field dư.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )

    fullName: str = Field(
        min_length=2,
        max_length=255
    )

    phoneNumber: str | None = Field(
        default=None,
        max_length=20
    )

    provinceCode: str | None = Field(
        default=None,
        max_length=20
    )

    province: str = Field(
        min_length=1,
        max_length=100
    )

    wardCode: str | None = Field(
        default=None,
        max_length=20
    )

    ward: str | None = Field(
        default=None,
        max_length=100
    )

    addressDetail: str | None = Field(
        default=None,
        max_length=255
    )

    storeName: str = Field(
        min_length=1,
        max_length=255
    )

    businessField: str = Field(
        min_length=1,
        max_length=100
    )

    # Hiện tại chỉ hỗ trợ Tiểu thương
    accountType: Literal["business"] = "business"

    @field_validator(
        "fullName",
        "province",
        "storeName",
        "businessField",
        mode="before"
    )
    @classmethod
    def validate_required_strings(cls, value):
        if value is None:
            raise ValueError(
                "Trường này không được để trống"
            )

        value = str(value).strip()

        if not value:
            raise ValueError(
                "Trường này không được để trống"
            )

        return value

    @field_validator(
        "phoneNumber",
        "provinceCode",
        "wardCode",
        "ward",
        "addressDetail",
        mode="before"
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        if value is None:
            return None

        value = str(value).strip()

        return value if value else None


# ============================================================
# LOGIN
# ============================================================

class LoginRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128
    )


# ============================================================
# SEND OTP
# ============================================================

class SendOTPRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    purpose: Literal[
        "verify_email",
        "forgot_password"
    ]


# ============================================================
# VERIFY OTP
# ============================================================

class VerifyOTPRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    code: str = Field(
        min_length=6,
        max_length=6
    )

    purpose: Literal[
        "verify_email",
        "forgot_password"
    ]

    @field_validator("code", mode="before")
    @classmethod
    def validate_otp_code(cls, value):
        value = str(value).strip()

        if not value.isdigit():
            raise ValueError(
                "Mã OTP phải gồm 6 chữ số"
            )

        if len(value) != 6:
            raise ValueError(
                "Mã OTP phải gồm 6 chữ số"
            )

        return value


# ============================================================
# RESET PASSWORD
# ============================================================

class ResetPasswordRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    resetToken: str = Field(
        min_length=1
    )

    newPassword: str = Field(
        min_length=8,
        max_length=128
    )


# ============================================================
# GOOGLE LOGIN
# ============================================================

class GoogleLoginRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    # Google ID Token
    idToken: str | None = None

    # Authorization Code flow
    code: str | None = None

    redirectUri: str | None = None

    codeVerifier: str | None = None


# ============================================================
# UPDATE PROFILE
# ============================================================

class UpdateProfileRequest(BaseModel):
    """
    Update thông tin profile.

    Không cho phép:
        - email
        - password
        - accountType
        - role
        - isVerified
        - googleId

    Cho phép:
        - fullName
        - phoneNumber
        - provinceCode
        - province
        - wardCode
        - ward
        - addressDetail
        - storeName
        - businessField
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    fullName: str | None = Field(
        default=None,
        min_length=2,
        max_length=255
    )

    phoneNumber: str | None = Field(
        default=None,
        max_length=20
    )

    provinceCode: str | None = Field(
        default=None,
        max_length=20
    )

    province: str | None = Field(
        default=None,
        max_length=100
    )

    wardCode: str | None = Field(
        default=None,
        max_length=20
    )

    ward: str | None = Field(
        default=None,
        max_length=100
    )

    addressDetail: str | None = Field(
        default=None,
        max_length=255
    )

    storeName: str | None = Field(
        default=None,
        max_length=255
    )

    businessField: str | None = Field(
        default=None,
        max_length=100
    )

    @field_validator(
        "fullName",
        "phoneNumber",
        "provinceCode",
        "province",
        "wardCode",
        "ward",
        "addressDetail",
        "storeName",
        "businessField",
        mode="before"
    )
    @classmethod
    def normalize_strings(cls, value):

        if value is None:
            return None

        return str(value).strip()