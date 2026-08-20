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


# CREATE SUPPLIER
class CreateSupplierRequest(BaseModel):
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

    productGroup: Optional[str] = Field(
        default=None,
        max_length=100
    )

    taxCode: Optional[str] = Field(
        default=None,
        max_length=50
    )

    note: Optional[str] = None

    @field_validator(
        "phoneNumber",
        "address",
        "productGroup",
        "taxCode",
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
                "Tên nhà cung cấp phải có ít nhất 2 ký tự"
            )

        return value


# UPDATE SUPPLIER
class UpdateSupplierRequest(BaseModel):
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

    productGroup: Optional[str] = Field(
        default=None,
        max_length=100
    )

    taxCode: Optional[str] = Field(
        default=None,
        max_length=50
    )

    note: Optional[str] = None

    @field_validator(
        "phoneNumber",
        "address",
        "productGroup",
        "taxCode",
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
                "Tên nhà cung cấp phải có ít nhất 2 ký tự"
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


# SUPPLIER RESPONSE
class SupplierResponse(BaseModel):
    supplierId: int

    name: str

    phoneNumber: Optional[str] = None

    email: Optional[str] = None

    address: Optional[str] = None

    productGroup: Optional[str] = None

    taxCode: Optional[str] = None

    note: Optional[str] = None

    createdAt: Optional[datetime] = None

    updatedAt: Optional[datetime] = None


# SUPPLIER LIST ITEM
class SupplierListItemResponse(BaseModel):
    supplierId: int

    name: str

    phoneNumber: Optional[str] = None

    productGroup: Optional[str] = None

    purchaseCount: int = 0

    totalDebt: float = 0


# SUPPLIER SUMMARY
class SupplierSummaryResponse(BaseModel):
    totalSuppliers: int = 0

    suppliersWithDebt: int = 0

    totalDebt: float = 0