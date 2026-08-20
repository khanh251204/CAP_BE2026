from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator
)


# CREATE CUSTOMER
class CreateCustomerRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    name: str = Field(
        min_length=2,
        max_length=255
    )

    phoneNumber: Optional[str] = Field(
        default=None,
        max_length=20
    )

    email: Optional[EmailStr] = None

    address: Optional[str] = Field(
        default=None,
        max_length=255
    )

    note: Optional[str] = None

    @field_validator(
        "phoneNumber",
        "address",
        "note",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(
        cls,
        value
    ):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    @field_validator(
        "email",
        mode="before"
    )
    @classmethod
    def empty_email_to_none(
        cls,
        value
    ):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    @field_validator(
        "name"
    )
    @classmethod
    def validate_name(
        cls,
        value: str
    ):
        value = value.strip()

        if len(value) < 2:
            raise ValueError(
                "Tên khách hàng phải có ít nhất 2 ký tự"
            )

        return value


# UPDATE CUSTOMER
class UpdateCustomerRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255
    )

    phoneNumber: Optional[str] = Field(
        default=None,
        max_length=20
    )

    email: Optional[EmailStr] = None

    address: Optional[str] = Field(
        default=None,
        max_length=255
    )

    note: Optional[str] = None

    @field_validator(
        "phoneNumber",
        "address",
        "note",
        mode="before"
    )
    @classmethod
    def empty_string_to_none(
        cls,
        value
    ):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    @field_validator(
        "email",
        mode="before"
    )
    @classmethod
    def empty_email_to_none(
        cls,
        value
    ):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    @field_validator(
        "name"
    )
    @classmethod
    def validate_name(
        cls,
        value
    ):
        if value is None:
            return value

        value = value.strip()

        if len(value) < 2:
            raise ValueError(
                "Tên khách hàng phải có ít nhất 2 ký tự"
            )

        return value

    @model_validator(
        mode="after"
    )
    def validate_update_data(
        self
    ):
        if not self.model_fields_set:
            raise ValueError(
                "Không có dữ liệu cần cập nhật"
            )

        return self


# CUSTOMER RESPONSE
class CustomerResponse(BaseModel):
    customerId: int

    name: str

    phoneNumber: Optional[str] = None

    email: Optional[str] = None

    address: Optional[str] = None

    note: Optional[str] = None

    createdAt: Optional[datetime] = None

    updatedAt: Optional[datetime] = None


# CUSTOMER LIST ITEM
class CustomerListItemResponse(BaseModel):
    customerId: int

    name: str

    phoneNumber: Optional[str] = None

    transactionCount: int = 0

    totalDebt: float = 0


# CUSTOMER SUMMARY
class CustomerSummaryResponse(BaseModel):
    totalCustomers: int = 0

    customersWithDebt: int = 0

    totalDebt: float = 0