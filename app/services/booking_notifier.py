from collections import defaultdict

from fastapi import WebSocket

from app.schemas.booking import BookingRead


class ProviderBookingNotifier:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, provider_profile_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[provider_profile_id].add(websocket)

    def disconnect(self, provider_profile_id: int, websocket: WebSocket) -> None:
        self._connections[provider_profile_id].discard(websocket)
        if not self._connections[provider_profile_id]:
            self._connections.pop(provider_profile_id, None)

    async def notify_booking_created(
        self,
        *,
        provider_profile_id: int,
        booking: BookingRead,
    ) -> None:
        stale_connections: list[WebSocket] = []
        for websocket in self._connections.get(provider_profile_id, set()):
            try:
                await websocket.send_json(
                    {
                        "type": "booking_created",
                        "booking": booking.model_dump(mode="json", by_alias=True),
                    }
                )
            except RuntimeError:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(provider_profile_id, websocket)


provider_booking_notifier = ProviderBookingNotifier()
