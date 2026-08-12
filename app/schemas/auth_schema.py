from typing import Literal, Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    model_validator
)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

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
    def validate_business_account(self):

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


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128
    )