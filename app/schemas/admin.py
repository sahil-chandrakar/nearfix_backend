from datetime import datetime

from pydantic import Field

from app.models.user import UserRole
from app.schemas.base import CamelModel
from app.schemas.booking import BookingRead
from app.schemas.provider import ProviderProfileRead


class AdminLoginRequest(CamelModel):
    phone: str = Field(pattern=r"^\d{10}$")
    password: str = Field(min_length=8, max_length=128)


class AdminSummary(CamelModel):
    total_customers: int
    total_providers: int
    pending_providers: int
    approved_providers: int
    rejected_providers: int
    pending_document_requests: int
    total_bookings: int
    pending_bookings: int
    accepted_bookings: int
    declined_bookings: int
    active_banners: int
    active_services: int


class AdminProviderRead(ProviderProfileRead):
    category_slugs: list[str]
    user_is_active: bool


class AdminCustomerPhoneHistoryRead(CamelModel):
    id: int
    old_phone: str | None
    new_phone: str
    changed_at: datetime


class AdminCustomerRead(CamelModel):
    id: int
    email: str | None
    phone: str | None
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    phone_history: list[AdminCustomerPhoneHistoryRead] = []


class UserActiveUpdate(CamelModel):
    is_active: bool


class UserPasswordReset(CamelModel):
    new_password: str = Field(min_length=8, max_length=128)


class AdminAuditLogRead(CamelModel):
    id: int
    admin_user_id: int | None
    action: str
    target_type: str
    target_id: str | None
    metadata: dict | None
    created_at: datetime


class AdminBookingRead(BookingRead):
    pass
