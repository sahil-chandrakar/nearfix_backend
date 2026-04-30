from pydantic import Field

from app.schemas.base import CamelModel


class CustomerRegisterRequest(CamelModel):
    name: str = Field(min_length=2, max_length=255)
    phone: str = Field(pattern=r"^\d{10}$")
    password: str = Field(min_length=8, max_length=128)


class PhoneLoginRequest(CamelModel):
    phone: str = Field(pattern=r"^\d{10}$")
    password: str = Field(min_length=8, max_length=128)


class CustomerProfileUpdate(CamelModel):
    name: str = Field(min_length=2, max_length=255)
    phone: str = Field(pattern=r"^\d{10}$")
