from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class BrandRead(CamelModel):
    id: int
    slug: str
    name: str
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class BrandCreate(CamelModel):
    name: str = Field(min_length=2, max_length=255)


class BrandUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
    display_order: int | None = None


class BrandServiceRead(CamelModel):
    id: int
    brand_id: int
    category_slug: str
    label: str
    label_hi: str
    group: str
    group_hi: str
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class BrandServiceCreate(CamelModel):
    category_slug: str = Field(min_length=1, max_length=100)


class BrandServiceUpdate(CamelModel):
    is_active: bool | None = None
    display_order: int | None = None


class BrandStoreRead(CamelModel):
    id: int
    brand_service_id: int
    store_type: Literal["provider", "manual"]
    provider_profile_id: int | None
    shop_name: str
    contact_name: str
    phone: str
    email: str | None
    latitude: float | None
    longitude: float | None
    is_active: bool
    display_order: int
    distance_km: float | None = None
    created_at: datetime
    updated_at: datetime


class BrandProviderStoreCreate(CamelModel):
    provider_profile_id: int
    display_order: int | None = None


class BrandManualStoreCreate(CamelModel):
    shop_name: str = Field(min_length=2, max_length=255)
    contact_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(pattern=r"^\d{10}$")
    email: EmailStr | None = None
    latitude: float | None = None
    longitude: float | None = None
    display_order: int | None = None


class BrandStoreUpdate(CamelModel):
    shop_name: str | None = Field(default=None, min_length=2, max_length=255)
    contact_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    email: EmailStr | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool | None = None
    display_order: int | None = None
