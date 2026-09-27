from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    fullName: Optional[str] = Field(default=None, min_length=2, max_length=255, alias="full_name")
    phone: Optional[str] = Field(default=None, max_length=20, alias="phone_number")
    phoneNumber: Optional[str] = Field(default=None, max_length=20)
    province: Optional[str] = Field(default=None, max_length=100, alias="region")
    region: Optional[str] = Field(default=None, max_length=100)
    accountType: Optional[Literal["personal", "business"]] = Field(default=None, alias="account_type")
    storeName: Optional[str] = Field(default=None, max_length=255, alias="store_name")
    businessField: Optional[str] = Field(default=None, max_length=100, alias="business_type")
    businessType: Optional[str] = Field(default=None, max_length=100)
    provinceCode: Optional[str] = Field(default=None, max_length=20, alias="province_code")
    wardCode: Optional[str] = Field(default=None, max_length=20, alias="ward_code")
    wardName: Optional[str] = Field(default=None, max_length=150, alias="ward_name")
    addressDetail: Optional[str] = Field(default=None, max_length=255, alias="address_detail")

    @model_validator(mode="after")
    def validate_profile(self):
        effective_phone = self.phoneNumber or self.phone
        if effective_phone is not None:
            clean_phone = effective_phone.strip()
            self.phone = clean_phone
            self.phoneNumber = clean_phone

        effective_province = self.province or self.region
        if effective_province is not None:
            clean_province = effective_province.strip()
            self.province = clean_province
            self.region = clean_province

        effective_business = self.businessField or self.businessType
        if effective_business is not None:
            clean_type = effective_business.strip().upper()
            allowed_types = {"RESELLER", "PRODUCER", "SERVICE"}
            if clean_type not in allowed_types:
                raise ValueError(
                    "Lĩnh vực kinh doanh chỉ chấp nhận một trong các giá trị: RESELLER, PRODUCER, SERVICE"
                )
            self.businessField = clean_type
            self.businessType = clean_type

        return self
