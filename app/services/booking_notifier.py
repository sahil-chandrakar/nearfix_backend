from collections import defaultdict
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

from app.models.booking import BookingStatus
from app.models.user import User, UserRole
from app.schemas.booking import BookingRead


class AppNotificationNotifier:
    def __init__(self) -> None:
        self._customer_connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._provider_connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._admin_connections: set[WebSocket] = set()

    async def connect_customer(self, customer_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._customer_connections[customer_id].add(websocket)

    def disconnect_customer(self, customer_id: int, websocket: WebSocket) -> None:
        self._customer_connections[customer_id].discard(websocket)
        if not self._customer_connections[customer_id]:
            self._customer_connections.pop(customer_id, None)

    async def connect_provider(
        self,
        provider_profile_id: int,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()
        self._provider_connections[provider_profile_id].add(websocket)

    def disconnect_provider(self, provider_profile_id: int, websocket: WebSocket) -> None:
        self._provider_connections[provider_profile_id].discard(websocket)
        if not self._provider_connections[provider_profile_id]:
            self._provider_connections.pop(provider_profile_id, None)

    async def connect_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._admin_connections.add(websocket)

    def disconnect_admin(self, websocket: WebSocket) -> None:
        self._admin_connections.discard(websocket)

    async def connect(self, provider_profile_id: int, websocket: WebSocket) -> None:
        await self.connect_provider(provider_profile_id, websocket)

    def disconnect(self, provider_profile_id: int, websocket: WebSocket) -> None:
        self.disconnect_provider(provider_profile_id, websocket)

    async def notify_booking_created(
        self,
        *,
        provider_profile_id: int,
        booking: BookingRead,
    ) -> None:
        payload = self._payload(type_="booking_created", booking=booking)
        await self._send_to_provider(provider_profile_id, payload)
        await self._send_to_admins(payload)

    async def notify_booking_status_changed(self, *, booking: BookingRead) -> None:
        event_type_by_status = {
            BookingStatus.ACCEPTED: "booking_accepted",
            BookingStatus.DECLINED: "booking_declined",
        }
        event_type = event_type_by_status.get(booking.status)
        if event_type is None:
            return

        payload = self._payload(type_=event_type, booking=booking)
        await self._send_to_customer(booking.customer_id, payload)
        await self._send_to_admins(payload)

    async def notify_user_logged_in(self, *, user: User) -> None:
        if user.role not in {UserRole.CUSTOMER.value, UserRole.PROVIDER.value}:
            return

        payload = {
            "type": "user_logged_in",
            "user": {
                "id": user.id,
                "role": user.role,
                "displayName": self._user_display_name(user),
            },
            "occurredAt": datetime.now(timezone.utc).isoformat(),
        }
        await self._send_to_admins(payload)

    def _payload(self, *, type_: str, booking: BookingRead) -> dict[str, object]:
        return {
            "type": type_,
            "booking": booking.model_dump(mode="json", by_alias=True),
        }

    def _user_display_name(self, user: User) -> str:
        return user.full_name or user.phone or user.email or f"User #{user.id}"

    async def _send_to_customer(
        self,
        customer_id: int,
        payload: dict[str, object],
    ) -> None:
        stale_connections = await self._send_to_connections(
            self._customer_connections.get(customer_id, set()),
            payload,
        )
        for websocket in stale_connections:
            self.disconnect_customer(customer_id, websocket)

    async def _send_to_provider(
        self,
        provider_profile_id: int,
        payload: dict[str, object],
    ) -> None:
        stale_connections = await self._send_to_connections(
            self._provider_connections.get(provider_profile_id, set()),
            payload,
        )
        for websocket in stale_connections:
            self.disconnect_provider(provider_profile_id, websocket)

    async def _send_to_admins(self, payload: dict[str, object]) -> None:
        stale_connections = await self._send_to_connections(
            self._admin_connections,
            payload,
        )
        for websocket in stale_connections:
            self.disconnect_admin(websocket)

    async def _send_to_connections(
        self,
        connections: set[WebSocket],
        payload: dict[str, object],
    ) -> list[WebSocket]:
        stale_connections: list[WebSocket] = []
        for websocket in list(connections):
            try:
                await websocket.send_json(payload)
            except (RuntimeError, WebSocketDisconnect):
                stale_connections.append(websocket)
        return stale_connections


app_notification_notifier = AppNotificationNotifier()
booking_cycle_notifier = app_notification_notifier
provider_booking_notifier = app_notification_notifier
