from datetime import datetime

from pydantic import EmailStr, Field

from app.models.user import UserRole
from app.schemas.base import CamelModel


class UserBase(CamelModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase):
    id: int
    role: UserRole
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
