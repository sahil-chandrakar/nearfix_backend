from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Token(CamelModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
