from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.models.provider_profile import ProviderVerificationStatus
from app.schemas.base import CamelModel


class ProviderRegistrationData(CamelModel):
    shop_company_name: str = Field(min_length=2, max_length=255)
    owner_name: str = Field(min_length=2, max_length=255)
    whatsapp_mobile_number: str = Field(pattern=r"^\d{10}$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    latitude: float | None = None
    longitude: float | None = None


class ProviderProfileRead(CamelModel):
    id: int
    user_id: int
    shop_company_name: str
    owner_name: str
    whatsapp_mobile_number: str
    email: EmailStr
    aadhaar_front_path: str
    aadhaar_back_path: str
    payment_bill_path: str
    electricity_bill_path: str
    latitude: float | None
    longitude: float | None
    verification_status: ProviderVerificationStatus
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ProviderVerificationUpdate(CamelModel):
    verification_status: ProviderVerificationStatus
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "ProviderVerificationUpdate":
        if (
            self.verification_status == ProviderVerificationStatus.REJECTED
            and not (self.reason or "").strip()
        ):
            raise ValueError("Rejection reason is required")
        return self


class ProviderProfileUpdate(CamelModel):
    shop_company_name: str = Field(min_length=2, max_length=255)
    owner_name: str = Field(min_length=2, max_length=255)
    whatsapp_mobile_number: str = Field(pattern=r"^\d{10}$")
    email: EmailStr
    latitude: float | None = None
    longitude: float | None = None


class ProviderPasswordUpdate(CamelModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
