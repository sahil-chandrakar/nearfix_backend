from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class BannerRead(CamelModel):
    id: int
    image_url: str
    alt_text: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BannerUpdate(CamelModel):
    alt_text: str | None = Field(default=None, min_length=1, max_length=255)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class BannerSettingsRead(CamelModel):
    banner_limit: int


class BannerSettingsUpdate(CamelModel):
    banner_limit: int = Field(ge=1, le=10)
