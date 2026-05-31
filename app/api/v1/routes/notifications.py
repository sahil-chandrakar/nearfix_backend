from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.provider_profile import ProviderVerificationStatus
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.booking_notifier import booking_cycle_notifier

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _user_from_token(db: Session, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        user_id = int(subject) if subject is not None else None
    except (InvalidTokenError, ValueError):
        return None

    if user_id is None:
        return None

    return UserRepository.get_by_id(db, user_id=user_id)


@router.websocket("/bookings/ws")
async def booking_notifications_websocket(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db),
) -> None:
    user = _user_from_token(db, token)
    if user is None or not user.is_active:
        await websocket.close(code=1008)
        return

    if user.role == UserRole.CUSTOMER.value:
        await booking_cycle_notifier.connect_customer(user.id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            booking_cycle_notifier.disconnect_customer(user.id, websocket)
        return

    if user.role == UserRole.PROVIDER.value:
        try:
            profile = AuthService.get_provider_profile(db=db, user_id=user.id)
        except HTTPException:
            await websocket.close(code=1008)
            return

        if profile.verification_status != ProviderVerificationStatus.APPROVED.value:
            await websocket.close(code=1008)
            return

        await booking_cycle_notifier.connect_provider(profile.id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            booking_cycle_notifier.disconnect_provider(profile.id, websocket)
        return

    if user.role == UserRole.ADMIN.value:
        await booking_cycle_notifier.connect_admin(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            booking_cycle_notifier.disconnect_admin(websocket)
        return

    await websocket.close(code=1008)
