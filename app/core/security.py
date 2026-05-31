from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
) -> str:
    to_encode: dict[str, Any] = {"sub": str(subject)}
    if expires_delta is not None:
        to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    elif settings.access_token_expire_minutes > 0:
        to_encode["exp"] = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
