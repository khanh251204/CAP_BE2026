from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


# REGISTER
class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fullName: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    accountType: Literal["personal", "business"]
    province: str = Field(min_length=2, max_length=100)
    storeName: Optional[str] = Field(default=None, max_length=255)
    businessField: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_business(self):
        if self.accountType == "business":
            if not self.storeName or not self.storeName.strip():
                raise ValueError("Tên cửa hàng/doanh nghiệp là bắt buộc")
            if not self.businessField or not self.businessField.strip():
                raise ValueError("Lĩnh vực kinh doanh là bắt buộc")

            allowed_types = {"RESELLER", "PRODUCER", "SERVICE"}
            clean_type = self.businessField.strip().upper()
            if clean_type not in allowed_types:
                raise ValueError(
                    "Lĩnh vực kinh doanh chỉ chấp nhận một trong các giá trị: RESELLER, PRODUCER, SERVICE"
                )
            self.businessField = clean_type

        return self


# LOGIN
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# SEND OTP
class SendOTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    purpose: Literal["verify_email", "forgot_password"]


# VERIFY OTP
class VerifyOTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: Literal["verify_email", "forgot_password"]


class VerifyForgotOTPRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


# RESET PASSWORD / FORGOT PASSWORD
class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    resetToken: Optional[str] = Field(default=None, alias="reset_token")
    token: Optional[str] = None
    email: Optional[EmailStr] = None
    otp: Optional[str] = Field(default=None, alias="code")
    newPassword: Optional[str] = Field(default=None, alias="new_password")
    password: Optional[str] = None

    @model_validator(mode="after")
    def resolve_fields(self):
        effective_token = self.resetToken or self.token
        if effective_token:
            clean_token = effective_token.strip()
            if clean_token.lower() not in ("cookie", "undefined", "null"):
                self.resetToken = clean_token
            else:
                self.resetToken = None

        if self.email:
            self.email = self.email.strip().lower()

        if self.otp:
            self.otp = str(self.otp).strip()

        effective_password = self.newPassword or self.password
        if not effective_password:
            raise ValueError("Mật khẩu mới là bắt buộc")
        if len(effective_password) < 8 or len(effective_password) > 128:
            raise ValueError("Mật khẩu phải có từ 8 đến 128 ký tự")
        self.newPassword = effective_password
        return self


# FORGOT PASSWORD (ALIAS)
ForgotPasswordRequest = ResetPasswordRequest


# CHANGE PASSWORD
class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    oldPassword: Optional[str] = Field(default=None, alias="old_password")
    currentPassword: Optional[str] = Field(default=None, alias="current_password")
    newPassword: Optional[str] = Field(default=None, alias="new_password")
    password: Optional[str] = None
    confirmPassword: Optional[str] = Field(default=None, alias="confirm_password")

    @model_validator(mode="after")
    def validate_fields(self):
        old_pwd = self.oldPassword or self.currentPassword
        if old_pwd:
            self.oldPassword = old_pwd

        new_pwd = self.newPassword or self.password
        if not new_pwd:
            raise ValueError("Mật khẩu mới là bắt buộc")
        if len(new_pwd) < 8 or len(new_pwd) > 128:
            raise ValueError("Mật khẩu mới phải từ 8 đến 128 ký tự")
        self.newPassword = new_pwd

        if self.confirmPassword is not None and self.confirmPassword != self.newPassword:
            raise ValueError("Mật khẩu xác nhận không khớp")

        return self


# GOOGLE
class GoogleLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idToken: str = Field(min_length=1)
