from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class SupportDetailsRead(CamelModel):
    footer_site_name: str
    admin_phone: str
    email: EmailStr
    help_heading_en: str
    help_heading_hi: str
    help_description_en: str
    help_description_hi: str


class SupportDetailsUpdate(CamelModel):
    footer_site_name: str = Field(min_length=1, max_length=80)
    admin_phone: str = Field(pattern=r"^\d{10}$")
    email: EmailStr
    help_heading_en: str = Field(min_length=1, max_length=120)
    help_heading_hi: str = Field(min_length=1, max_length=120)
    help_description_en: str = Field(min_length=1, max_length=500)
    help_description_hi: str = Field(min_length=1, max_length=500)
