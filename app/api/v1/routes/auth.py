from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DBSession
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService
from app.services.booking_notifier import app_notification_notifier

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate, db: DBSession) -> UserRead:
    return AuthService.register_user(db=db, payload=payload)


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: DBSession) -> Token:
    user = AuthService.authenticate_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )
    await app_notification_notifier.notify_user_logged_in(user=user)
    return Token(access_token=create_access_token(subject=user.id))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> UserRead:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> None:
    return None
