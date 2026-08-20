from typing import Literal, Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    model_validator
)

from typing import (
    Literal,
    Optional
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field
)

# UPDATE PROFILE
class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    fullName: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255
    )

    phoneNumber: Optional[str] = Field(
        default=None,
        max_length=20
    )

    provinceCode: Optional[str] = Field(
        default=None,
        max_length=20
    )

    province: Optional[str] = Field(
        default=None,
        max_length=100
    )

    wardCode: Optional[str] = Field(
        default=None,
        max_length=20
    )

    ward: Optional[str] = Field(
        default=None,
        max_length=150
    )

    addressDetail: Optional[str] = Field(
        default=None,
        max_length=255
    )

    accountType: Optional[
        Literal[
            "personal",
            "business"
        ]
    ] = None

    storeName: Optional[str] = Field(
        default=None,
        max_length=255
    )

    businessField: Optional[str] = Field(
        default=None,
        max_length=100
    )

# REGISTER
class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fullName: str = Field(
        min_length=2,
        max_length=255
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )

    accountType: Literal[
        "personal",
        "business"
    ]

    province: str = Field(
        min_length=2,
        max_length=100
    )

    storeName: Optional[str] = Field(
        default=None,
        max_length=255
    )

    businessField: Optional[str] = Field(
        default=None,
        max_length=100
    )

    @model_validator(mode="after")
    def validate_business(self):
        if self.accountType == "business":

            if (
                not self.storeName
                or not self.storeName.strip()
            ):
                raise ValueError(
                    "Tên cửa hàng/doanh nghiệp là bắt buộc"
                )

            if (
                not self.businessField
                or not self.businessField.strip()
            ):
                raise ValueError(
                    "Lĩnh vực kinh doanh là bắt buộc"
                )

        return self


# LOGIN
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128
    )


# SEND OTP
class SendOTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    purpose: Literal[
        "verify_email",
        "forgot_password"
    ]


# VERIFY OTP
class VerifyOTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$"
    )

    purpose: Literal[
        "verify_email",
        "forgot_password"
    ]


# RESET PASSWORD
class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resetToken: str = Field(
        min_length=1
    )

    newPassword: str = Field(
        min_length=8,
        max_length=128
    )

# GOOGLE
class GoogleLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idToken: str = Field(
        min_length=1
    )