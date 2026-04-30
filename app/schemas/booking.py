from datetime import datetime
from pydantic import Field

from app.models.booking import BookingStatus
from app.schemas.base import CamelModel


class BookingCreate(CamelModel):
    provider_profile_id: int
    category_slug: str = Field(min_length=1, max_length=80)
    latitude: float | None = None
    longitude: float | None = None


class BookingStatusUpdate(CamelModel):
    status: BookingStatus


class BookingRead(CamelModel):
    id: int
    customer_id: int
    provider_profile_id: int
    category_slug: str
    service_label: str
    status: BookingStatus
    customer_phone: str | None
    customer_name: str | None
    provider_phone: str
    shop_company_name: str
    owner_name: str
    distance_km: float | None
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
