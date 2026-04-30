from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

DBSession = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def get_current_user(db: DBSession, credentials: BearerCredentials) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
        user_id = int(subject) if subject is not None else None
    except (InvalidTokenError, ValueError):
        raise credentials_exception from None

    if user_id is None:
        raise credentials_exception

    user = UserRepository.get_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    allowed_roles = {role.value for role in roles}

    def role_dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_dependency


CustomerUser = Annotated[User, Depends(require_role(UserRole.CUSTOMER))]
ProviderUser = Annotated[User, Depends(require_role(UserRole.PROVIDER))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
