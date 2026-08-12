from typing import Literal, Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict
)


class RegisterRequest(BaseModel):
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

    phoneNumber: Optional[str] = Field(
        default=None,
        max_length=20
    )

    province: Optional[str] = Field(
        default=None,
        max_length=100
    )

    businessField: Optional[str] = Field(
        default=None,
        max_length=100
    )

    accountType: Literal[
        "personal",
        "business"
    ] = "personal"


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128
    )