from collections.abc import Generator
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app import models  # noqa: F401
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.booking import Booking
from app.models.customer_home_banner import CustomerHomeBanner
from app.models.provider_document_change_request import ProviderDocumentChangeRequest
from app.models.provider_profile import ProviderProfile, ProviderVerificationStatus
from app.models.user import User, UserRole
from app.models.user_phone_history import UserPhoneHistory
from app.services.booking_notifier import app_notification_notifier
from app.services.upload_service import UploadService


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def with_test_db(callback) -> None:
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        callback(db)
    finally:
        db_generator.close()


def register_customer(client: TestClient, phone: str = "7970054811") -> str:
    response = client.post(
        "/api/v1/customer/register",
        json={
            "name": "Test Customer",
            "phone": phone,
            "password": "password123",
        },
    )
    assert response.status_code == 201
    return response.json()["accessToken"]


def provider_files() -> dict[str, tuple[str, bytes, str]]:
    jpg_bytes = b"\xff\xd8\xff\xe0nearfix-test\xff\xd9"
    return {
        "aadhaarFront": ("aadhaar-front.jpg", jpg_bytes, "image/jpeg"),
        "aadhaarBack": ("aadhaar-back.jpg", jpg_bytes, "image/jpeg"),
        "paymentBill": ("payment-bill.jpg", jpg_bytes, "image/jpeg"),
        "electricityBill": ("electricity-bill.jpg", jpg_bytes, "image/jpeg"),
    }


def register_provider(client: TestClient, phone: str = "7970054822") -> str:
    response = client.post(
        "/api/v1/provider/register",
        data={
            "shopCompanyName": "NearFix Test Shop",
            "ownerName": "Provider Owner",
            "whatsappMobileNumber": phone,
            "email": f"{phone}@example.com",
            "password": "password123",
            "latitude": "20.5937",
            "longitude": "78.9629",
        },
        files=provider_files(),
    )
    assert response.status_code == 201
    return response.json()["accessToken"]


def update_first_provider_status(
    status: ProviderVerificationStatus,
    reason: str | None = None,
) -> None:
    def update_provider(db):
        profile = db.query(ProviderProfile).first()
        profile.verification_status = status.value
        profile.rejection_reason = reason
        db.add(profile)
        db.commit()

    with_test_db(update_provider)


def create_admin_token(client: TestClient, phone: str = "7970054899") -> str:
    def create_admin(db):
        admin = User(
            email=f"{phone}@admin.example.com",
            phone=phone,
            full_name="Admin",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN.value,
            is_superuser=True,
        )
        db.add(admin)
        db.commit()

    with_test_db(create_admin)

    login_response = client.post(
        "/api/v1/admin/login",
        json={"phone": phone, "password": "password123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["accessToken"]


def test_access_token_has_no_exp_when_expiry_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "access_token_expire_minutes", 0)

    token = create_access_token(subject=123)
    payload = decode_access_token(token)

    assert payload["sub"] == "123"
    assert "exp" not in payload


def test_access_token_keeps_exp_when_expiry_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "access_token_expire_minutes", 60)

    token = create_access_token(subject=123)
    payload = decode_access_token(token)

    assert payload["sub"] == "123"
    assert "exp" in payload


def test_expired_legacy_token_returns_unauthorized(client: TestClient) -> None:
    active_token = register_customer(client)
    user_response = client.get("/api/v1/auth/me", headers=auth_headers(active_token))
    assert user_response.status_code == 200

    expired_token = create_access_token(
        subject=user_response.json()["id"],
        expires_delta=timedelta(minutes=-1),
    )

    expired_response = client.get("/api/v1/auth/me", headers=auth_headers(expired_token))
    assert expired_response.status_code == 401


def test_customer_register_login_and_me(client: TestClient) -> None:
    token = register_customer(client)

    me_response = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me_response.status_code == 200
    assert me_response.json()["phone"] == "7970054811"
    assert me_response.json()["role"] == "customer"

    login_response = client.post(
        "/api/v1/customer/login",
        json={"phone": "7970054811", "password": "password123"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["tokenType"] == "bearer"


def test_customer_can_update_profile_and_phone_history_is_saved(
    client: TestClient,
) -> None:
    token = register_customer(client)

    response = client.patch(
        "/api/v1/customer/me",
        headers=auth_headers(token),
        json={"name": "Updated Customer", "phone": "7970054812"},
    )

    assert response.status_code == 200
    assert response.json()["fullName"] == "Updated Customer"
    assert response.json()["phone"] == "7970054812"

    def assert_history(db):
        history = db.query(UserPhoneHistory).all()
        assert len(history) == 1
        assert history[0].old_phone == "7970054811"
        assert history[0].new_phone == "7970054812"

    with_test_db(assert_history)


def test_duplicate_customer_phone_returns_conflict(client: TestClient) -> None:
    register_customer(client)

    response = client.post(
        "/api/v1/customer/register",
        json={
            "name": "Second Customer",
            "phone": "7970054811",
            "password": "password123",
        },
    )

    assert response.status_code == 409


def test_customer_login_with_wrong_password_returns_unauthorized(client: TestClient) -> None:
    register_customer(client)

    response = client.post(
        "/api/v1/customer/login",
        json={"phone": "7970054811", "password": "wrongpass123"},
    )

    assert response.status_code == 401


def test_provider_register_login_and_profile(client: TestClient) -> None:
    token = register_provider(client)

    profile_response = client.get("/api/v1/provider/me", headers=auth_headers(token))
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["shopCompanyName"] == "NearFix Test Shop"
    assert profile["verificationStatus"] == "pending"
    assert profile["aadhaarFrontPath"].endswith(".jpg")

    login_response = client.post(
        "/api/v1/provider/login",
        json={"phone": "7970054822", "password": "password123"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["tokenType"] == "bearer"


def test_provider_can_save_categories(client: TestClient) -> None:
    token = register_provider(client)

    save_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(token),
        json={"categorySlugs": ["plumber", "house-cleaning", "mens-grooming"]},
    )
    assert save_response.status_code == 200
    assert save_response.json()["categorySlugs"] == [
        "house-cleaning",
        "mens-grooming",
        "plumber",
    ]

    read_response = client.get(
        "/api/v1/provider/categories",
        headers=auth_headers(token),
    )
    assert read_response.status_code == 200
    assert read_response.json()["categorySlugs"] == [
        "house-cleaning",
        "mens-grooming",
        "plumber",
    ]


def test_invalid_provider_category_slug_returns_validation_error(
    client: TestClient,
) -> None:
    token = register_provider(client)

    response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(token),
        json={"categorySlugs": ["not-real"]},
    )

    assert response.status_code == 422


def test_rejected_provider_can_only_read_status_surface(client: TestClient) -> None:
    token = register_provider(client)
    update_first_provider_status(
        ProviderVerificationStatus.REJECTED,
        reason="Documents are not readable",
    )

    login_response = client.post(
        "/api/v1/provider/login",
        json={"phone": "7970054822", "password": "password123"},
    )
    assert login_response.status_code == 200

    profile_response = client.get("/api/v1/provider/me", headers=auth_headers(token))
    assert profile_response.status_code == 200
    assert profile_response.json()["verificationStatus"] == "rejected"
    assert profile_response.json()["rejectionReason"] == "Documents are not readable"

    category_read_response = client.get(
        "/api/v1/provider/categories",
        headers=auth_headers(token),
    )
    assert category_read_response.status_code == 200

    category_update_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(token),
        json={"categorySlugs": ["plumber"]},
    )
    assert category_update_response.status_code == 403

    bookings_response = client.get(
        "/api/v1/provider/bookings?status=pending",
        headers=auth_headers(token),
    )
    assert bookings_response.status_code == 403

    profile_update_response = client.patch(
        "/api/v1/provider/me",
        headers=auth_headers(token),
        json={
            "shopCompanyName": "Rejected Shop",
            "ownerName": "Rejected Owner",
            "whatsappMobileNumber": "7970054822",
            "email": "7970054822@example.com",
            "latitude": 20.5937,
            "longitude": 78.9629,
        },
    )
    assert profile_update_response.status_code == 403

    documents_response = client.get(
        "/api/v1/provider/document-change-requests",
        headers=auth_headers(token),
    )
    assert documents_response.status_code == 403


def test_pending_provider_with_categories_cannot_use_operational_provider_apis(
    client: TestClient,
) -> None:
    token = register_provider(client)

    save_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(token),
        json={"categorySlugs": ["plumber"]},
    )
    assert save_response.status_code == 200

    bookings_response = client.get(
        "/api/v1/provider/bookings?status=pending",
        headers=auth_headers(token),
    )
    assert bookings_response.status_code == 403

    password_response = client.patch(
        "/api/v1/provider/password",
        headers=auth_headers(token),
        json={
            "currentPassword": "password123",
            "newPassword": "password456",
        },
    )
    assert password_response.status_code == 403


def test_customer_provider_search_filters_approved_category_and_distance(
    client: TestClient,
) -> None:
    provider_token = register_provider(client)
    customer_token = register_customer(client)

    category_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["plumber"]},
    )
    assert category_response.status_code == 200

    pending_response = client.get(
        "/api/v1/customer/providers?category=plumber&lat=20.6&lng=78.9",
        headers=auth_headers(customer_token),
    )
    assert pending_response.status_code == 200
    assert pending_response.json() == []

    def approve_provider(db):
        profile = db.query(ProviderProfile).first()
        profile.verification_status = ProviderVerificationStatus.APPROVED.value
        db.add(profile)
        db.commit()

    with_test_db(approve_provider)

    approved_response = client.get(
        "/api/v1/customer/providers?category=plumber&lat=20.6&lng=78.9",
        headers=auth_headers(customer_token),
    )
    assert approved_response.status_code == 200
    results = approved_response.json()
    assert len(results) == 1
    assert results[0]["shopCompanyName"] == "NearFix Test Shop"
    assert results[0]["distanceKm"] is not None


def test_customer_call_creates_pending_booking_and_provider_can_accept(
    client: TestClient,
) -> None:
    admin_token = create_admin_token(client)
    provider_token = register_provider(client)
    customer_token = register_customer(client)

    client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["bike-mechanic"]},
    )

    def approve_provider(db):
        profile = db.query(ProviderProfile).first()
        profile.verification_status = ProviderVerificationStatus.APPROVED.value
        db.add(profile)
        db.commit()

    with_test_db(approve_provider)

    initial_summary_response = client.get(
        "/api/v1/admin/summary",
        headers=auth_headers(admin_token),
    )
    assert initial_summary_response.status_code == 200
    initial_summary = initial_summary_response.json()
    assert initial_summary["totalBookings"] == 0
    assert initial_summary["pendingBookings"] == 0
    assert initial_summary["acceptedBookings"] == 0
    assert initial_summary["declinedBookings"] == 0

    create_response = client.post(
        "/api/v1/customer/bookings",
        headers=auth_headers(customer_token),
        json={
            "providerProfileId": 1,
            "categorySlug": "bike-mechanic",
            "latitude": 20.6,
            "longitude": 78.9,
        },
    )

    assert create_response.status_code == 201
    created_booking = create_response.json()
    assert created_booking["status"] == "pending"
    assert created_booking["serviceLabel"] == "Bike Mechanic"
    assert created_booking["distanceKm"] is not None

    created_summary_response = client.get(
        "/api/v1/admin/summary",
        headers=auth_headers(admin_token),
    )
    assert created_summary_response.status_code == 200
    created_summary = created_summary_response.json()
    assert created_summary["totalBookings"] == 1
    assert created_summary["pendingBookings"] == 1
    assert created_summary["acceptedBookings"] == 0
    assert created_summary["declinedBookings"] == 0

    pending_response = client.get(
        "/api/v1/provider/bookings?status=pending",
        headers=auth_headers(provider_token),
    )
    assert pending_response.status_code == 200
    assert len(pending_response.json()) == 1

    accept_response = client.patch(
        f"/api/v1/provider/bookings/{created_booking['id']}/status",
        headers=auth_headers(provider_token),
        json={"status": "accepted"},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    accepted_summary_response = client.get(
        "/api/v1/admin/summary",
        headers=auth_headers(admin_token),
    )
    assert accepted_summary_response.status_code == 200
    accepted_summary = accepted_summary_response.json()
    assert accepted_summary["totalBookings"] == 1
    assert accepted_summary["pendingBookings"] == 0
    assert accepted_summary["acceptedBookings"] == 1
    assert accepted_summary["declinedBookings"] == 0

    accepted_response = client.get(
        "/api/v1/provider/bookings?status=accepted",
        headers=auth_headers(provider_token),
    )
    assert accepted_response.status_code == 200
    assert len(accepted_response.json()) == 1


def test_provider_and_admin_receive_booking_created_notification(
    client: TestClient,
) -> None:
    admin_token = create_admin_token(client)
    provider_token = register_provider(client)
    customer_token = register_customer(client)

    client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["plumber"]},
    )
    update_first_provider_status(ProviderVerificationStatus.APPROVED)

    with (
        client.websocket_connect(
            f"/api/v1/notifications/bookings/ws?token={provider_token}",
        ) as provider_ws,
        client.websocket_connect(
            f"/api/v1/notifications/bookings/ws?token={admin_token}",
        ) as admin_ws,
    ):
        create_response = client.post(
            "/api/v1/customer/bookings",
            headers=auth_headers(customer_token),
            json={"providerProfileId": 1, "categorySlug": "plumber"},
        )

        assert create_response.status_code == 201
        created_booking = create_response.json()

        provider_message = provider_ws.receive_json()
        admin_message = admin_ws.receive_json()

    assert provider_message["type"] == "booking_created"
    assert provider_message["booking"]["id"] == created_booking["id"]
    assert admin_message["type"] == "booking_created"
    assert admin_message["booking"]["id"] == created_booking["id"]


def test_customer_and_admin_receive_booking_status_notifications(
    client: TestClient,
) -> None:
    admin_token = create_admin_token(client)
    provider_token = register_provider(client)
    customer_token = register_customer(client)

    client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["bike-mechanic", "plumber"]},
    )
    update_first_provider_status(ProviderVerificationStatus.APPROVED)

    first_create_response = client.post(
        "/api/v1/customer/bookings",
        headers=auth_headers(customer_token),
        json={"providerProfileId": 1, "categorySlug": "plumber"},
    )
    assert first_create_response.status_code == 201

    second_create_response = client.post(
        "/api/v1/customer/bookings",
        headers=auth_headers(customer_token),
        json={"providerProfileId": 1, "categorySlug": "bike-mechanic"},
    )
    assert second_create_response.status_code == 201

    first_booking_id = first_create_response.json()["id"]
    second_booking_id = second_create_response.json()["id"]

    with (
        client.websocket_connect(
            f"/api/v1/notifications/bookings/ws?token={customer_token}",
        ) as customer_ws,
        client.websocket_connect(
            f"/api/v1/notifications/bookings/ws?token={admin_token}",
        ) as admin_ws,
    ):
        accept_response = client.patch(
            f"/api/v1/provider/bookings/{first_booking_id}/status",
            headers=auth_headers(provider_token),
            json={"status": "accepted"},
        )
        assert accept_response.status_code == 200

        customer_accept_message = customer_ws.receive_json()
        admin_accept_message = admin_ws.receive_json()

        decline_response = client.patch(
            f"/api/v1/provider/bookings/{second_booking_id}/status",
            headers=auth_headers(provider_token),
            json={"status": "declined"},
        )
        assert decline_response.status_code == 200

        customer_decline_message = customer_ws.receive_json()
        admin_decline_message = admin_ws.receive_json()

    assert customer_accept_message["type"] == "booking_accepted"
    assert customer_accept_message["booking"]["id"] == first_booking_id
    assert admin_accept_message["type"] == "booking_accepted"
    assert admin_accept_message["booking"]["id"] == first_booking_id
    assert customer_decline_message["type"] == "booking_declined"
    assert customer_decline_message["booking"]["id"] == second_booking_id
    assert admin_decline_message["type"] == "booking_declined"
    assert admin_decline_message["booking"]["id"] == second_booking_id


def test_booking_notification_websocket_rejects_invalid_and_pending_provider(
    client: TestClient,
) -> None:
    provider_token = register_provider(client)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/notifications/bookings/ws?token=bad"):
            pass

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/notifications/bookings/ws?token={provider_token}",
        ):
            pass


def test_admin_receives_customer_and_provider_login_notifications(
    client: TestClient,
) -> None:
    admin_token = create_admin_token(client)
    register_customer(client)
    register_provider(client)

    with client.websocket_connect(
        f"/api/v1/notifications/bookings/ws?token={admin_token}",
    ) as admin_ws:
        customer_login_response = client.post(
            "/api/v1/customer/login",
            json={"phone": "7970054811", "password": "password123"},
        )
        assert customer_login_response.status_code == 200
        customer_message = admin_ws.receive_json()

        provider_login_response = client.post(
            "/api/v1/provider/login",
            json={"phone": "7970054822", "password": "password123"},
        )
        assert provider_login_response.status_code == 200
        provider_message = admin_ws.receive_json()

    assert customer_message["type"] == "user_logged_in"
    assert customer_message["user"]["role"] == "customer"
    assert customer_message["user"]["displayName"] == "Test Customer"
    assert isinstance(customer_message["user"]["id"], int)
    assert "occurredAt" in customer_message
    assert provider_message["type"] == "user_logged_in"
    assert provider_message["user"]["role"] == "provider"
    assert provider_message["user"]["displayName"] == "Provider Owner"
    assert isinstance(provider_message["user"]["id"], int)
    assert "occurredAt" in provider_message


def test_admin_receives_customer_and_provider_registration_login_notifications(
    client: TestClient,
) -> None:
    admin_token = create_admin_token(client)

    with client.websocket_connect(
        f"/api/v1/notifications/bookings/ws?token={admin_token}",
    ) as admin_ws:
        customer_register_response = client.post(
            "/api/v1/customer/register",
            json={
                "name": "New Customer",
                "phone": "7970054813",
                "password": "password123",
            },
        )
        assert customer_register_response.status_code == 201
        customer_message = admin_ws.receive_json()

        provider_register_response = client.post(
            "/api/v1/provider/register",
            data={
                "shopCompanyName": "New NearFix Shop",
                "ownerName": "New Provider",
                "whatsappMobileNumber": "7970054830",
                "email": "7970054830@example.com",
                "password": "password123",
                "latitude": "20.5937",
                "longitude": "78.9629",
            },
            files=provider_files(),
        )
        assert provider_register_response.status_code == 201
        provider_message = admin_ws.receive_json()

    assert customer_message["type"] == "user_logged_in"
    assert customer_message["user"]["role"] == "customer"
    assert customer_message["user"]["displayName"] == "New Customer"
    assert provider_message["type"] == "user_logged_in"
    assert provider_message["user"]["role"] == "provider"
    assert provider_message["user"]["displayName"] == "New Provider"


def test_admin_login_does_not_emit_login_notification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_admin_token(client)

    async def fail_if_called(*, user: User) -> None:
        raise AssertionError(f"Unexpected admin login notification for {user.id}")

    monkeypatch.setattr(
        app_notification_notifier,
        "notify_user_logged_in",
        fail_if_called,
    )

    login_response = client.post(
        "/api/v1/admin/login",
        json={"phone": "7970054899", "password": "password123"},
    )

    assert login_response.status_code == 200


def test_provider_can_decline_booking_and_declined_filter_shows_it(
    client: TestClient,
) -> None:
    provider_token = register_provider(client)
    customer_token = register_customer(client)

    client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["plumber"]},
    )

    def approve_provider(db):
        profile = db.query(ProviderProfile).first()
        profile.verification_status = ProviderVerificationStatus.APPROVED.value
        db.add(profile)
        db.commit()

    with_test_db(approve_provider)

    create_response = client.post(
        "/api/v1/customer/bookings",
        headers=auth_headers(customer_token),
        json={"providerProfileId": 1, "categorySlug": "plumber"},
    )
    assert create_response.status_code == 201

    decline_response = client.patch(
        f"/api/v1/provider/bookings/{create_response.json()['id']}/status",
        headers=auth_headers(provider_token),
        json={"status": "declined"},
    )
    assert decline_response.status_code == 200

    declined_response = client.get(
        "/api/v1/provider/bookings?status=declined",
        headers=auth_headers(provider_token),
    )
    assert declined_response.status_code == 200
    assert len(declined_response.json()) == 1


def test_provider_profile_password_and_document_request_flow(
    client: TestClient,
) -> None:
    provider_token = register_provider(client)
    update_first_provider_status(ProviderVerificationStatus.APPROVED)

    profile_response = client.patch(
        "/api/v1/provider/me",
        headers=auth_headers(provider_token),
        json={
            "shopCompanyName": "Updated Shop",
            "ownerName": "Updated Owner",
            "whatsappMobileNumber": "7970054833",
            "email": "updated@example.com",
            "latitude": 21.1,
            "longitude": 79.1,
        },
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["shopCompanyName"] == "Updated Shop"
    assert profile_response.json()["whatsappMobileNumber"] == "7970054833"

    password_response = client.patch(
        "/api/v1/provider/password",
        headers=auth_headers(provider_token),
        json={"currentPassword": "password123", "newPassword": "newpass123"},
    )
    assert password_response.status_code == 204

    login_response = client.post(
        "/api/v1/provider/login",
        json={"phone": "7970054833", "password": "newpass123"},
    )
    assert login_response.status_code == 200

    document_response = client.post(
        "/api/v1/provider/document-change-requests",
        headers=auth_headers(provider_token),
        files={
            "aadhaarFront": (
                "new-aadhaar-front.jpg",
                b"\xff\xd8\xff\xe0nearfix-doc\xff\xd9",
                "image/jpeg",
            )
        },
    )
    assert document_response.status_code == 201
    assert document_response.json()[0]["status"] == "pending"

    def create_admin(db):
        admin = User(
            email="docadmin@example.com",
            phone="7970054898",
            full_name="Doc Admin",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN.value,
            is_superuser=True,
        )
        db.add(admin)
        db.commit()

    with_test_db(create_admin)

    admin_login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "docadmin@example.com", "password": "password123"},
    )
    assert admin_login_response.status_code == 200
    admin_token = admin_login_response.json()["accessToken"]

    pending_response = client.get(
        "/api/v1/admin/provider-document-change-requests/pending",
        headers=auth_headers(admin_token),
    )
    assert pending_response.status_code == 200
    assert len(pending_response.json()) == 1

    request_file_response = client.get(
        "/api/v1/admin/provider-document-change-requests/1/file",
        headers=auth_headers(admin_token),
    )
    assert request_file_response.status_code == 200
    assert request_file_response.content == b"\xff\xd8\xff\xe0nearfix-doc\xff\xd9"

    approve_response = client.patch(
        "/api/v1/admin/provider-document-change-requests/1",
        headers=auth_headers(admin_token),
        json={"status": "approved"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    def assert_document_applied(db):
        request = db.query(ProviderDocumentChangeRequest).first()
        profile = db.query(ProviderProfile).first()
        assert request.status == "approved"
        assert profile.aadhaar_front_path == request.document_path

    with_test_db(assert_document_applied)

    provider_document_response = client.get(
        "/api/v1/admin/providers/1/documents/aadhaar_front",
        headers=auth_headers(admin_token),
    )
    assert provider_document_response.status_code == 200
    assert provider_document_response.content == b"\xff\xd8\xff\xe0nearfix-doc\xff\xd9"


def test_customer_bookings_requires_customer_auth(client: TestClient) -> None:
    provider_token = register_provider(client)

    response = client.get(
        "/api/v1/customer/bookings",
        headers=auth_headers(provider_token),
    )

    assert response.status_code == 403


def test_role_guards_reject_wrong_roles(client: TestClient) -> None:
    customer_token = register_customer(client)
    provider_token = register_provider(client)

    provider_only_response = client.get(
        "/api/v1/provider/me",
        headers=auth_headers(customer_token),
    )
    assert provider_only_response.status_code == 403

    admin_only_response = client.get(
        "/api/v1/admin/providers/pending",
        headers=auth_headers(provider_token),
    )
    assert admin_only_response.status_code == 403


def test_admin_can_list_pending_providers(client: TestClient) -> None:
    register_provider(client)
    admin_token = create_admin_token(client)

    response = client.get(
        "/api/v1/admin/providers/pending",
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_admin_rejects_provider_with_required_reason_and_audit_log(
    client: TestClient,
) -> None:
    provider_token = register_provider(client)
    admin_token = create_admin_token(client)

    missing_reason_response = client.patch(
        "/api/v1/admin/providers/1/verification-status",
        headers=auth_headers(admin_token),
        json={"verificationStatus": "rejected"},
    )
    assert missing_reason_response.status_code == 422

    reject_response = client.patch(
        "/api/v1/admin/providers/1/verification-status",
        headers=auth_headers(admin_token),
        json={
            "verificationStatus": "rejected",
            "reason": "Uploaded document is not readable",
        },
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["verificationStatus"] == "rejected"
    assert reject_response.json()["rejectionReason"] == "Uploaded document is not readable"

    provider_response = client.get("/api/v1/provider/me", headers=auth_headers(provider_token))
    assert provider_response.status_code == 200
    assert provider_response.json()["rejectionReason"] == "Uploaded document is not readable"

    def assert_audit_log(db):
        audit_log = db.query(AdminAuditLog).first()
        assert audit_log is not None
        assert audit_log.action == "provider_rejected"

    with_test_db(assert_audit_log)


def test_admin_can_reset_customer_password_and_audit_log_excludes_password(
    client: TestClient,
) -> None:
    register_customer(client)
    admin_token = create_admin_token(client)

    reset_response = client.patch(
        "/api/v1/admin/users/1/password",
        headers=auth_headers(admin_token),
        json={"newPassword": "newpass123"},
    )
    assert reset_response.status_code == 204

    old_login_response = client.post(
        "/api/v1/customer/login",
        json={"phone": "7970054811", "password": "password123"},
    )
    assert old_login_response.status_code == 401

    new_login_response = client.post(
        "/api/v1/customer/login",
        json={"phone": "7970054811", "password": "newpass123"},
    )
    assert new_login_response.status_code == 200

    def assert_audit_log(db):
        audit_log = db.query(AdminAuditLog).filter_by(action="user_password_reset").first()
        assert audit_log is not None
        assert audit_log.target_type == "user"
        assert audit_log.target_id == "1"
        assert "customer" in (audit_log.metadata_json or "")
        assert "newpass123" not in (audit_log.metadata_json or "")

    with_test_db(assert_audit_log)


def test_admin_can_reset_provider_password(client: TestClient) -> None:
    register_provider(client)
    admin_token = create_admin_token(client)

    reset_response = client.patch(
        "/api/v1/admin/users/1/password",
        headers=auth_headers(admin_token),
        json={"newPassword": "providerpass123"},
    )
    assert reset_response.status_code == 204

    old_login_response = client.post(
        "/api/v1/provider/login",
        json={"phone": "7970054822", "password": "password123"},
    )
    assert old_login_response.status_code == 401

    new_login_response = client.post(
        "/api/v1/provider/login",
        json={"phone": "7970054822", "password": "providerpass123"},
    )
    assert new_login_response.status_code == 200


def test_admin_password_reset_rejects_wrong_roles_inactive_and_invalid_payloads(
    client: TestClient,
) -> None:
    customer_token = register_customer(client)
    admin_token = create_admin_token(client)

    non_admin_response = client.patch(
        "/api/v1/admin/users/1/password",
        headers=auth_headers(customer_token),
        json={"newPassword": "newpass123"},
    )
    assert non_admin_response.status_code == 403

    short_password_response = client.patch(
        "/api/v1/admin/users/1/password",
        headers=auth_headers(admin_token),
        json={"newPassword": "short"},
    )
    assert short_password_response.status_code == 422

    missing_user_response = client.patch(
        "/api/v1/admin/users/999/password",
        headers=auth_headers(admin_token),
        json={"newPassword": "newpass123"},
    )
    assert missing_user_response.status_code == 404

    def deactivate_customer(db):
        customer = db.query(User).filter_by(phone="7970054811").one()
        customer.is_active = False
        db.add(customer)
        db.commit()

    with_test_db(deactivate_customer)

    inactive_response = client.patch(
        "/api/v1/admin/users/1/password",
        headers=auth_headers(admin_token),
        json={"newPassword": "newpass123"},
    )
    assert inactive_response.status_code == 400

    def admin_user_id(db):
        return db.query(User).filter_by(role=UserRole.ADMIN.value).one().id

    admin_id_holder: dict[str, int] = {}

    def capture_admin_id(db):
        admin_id_holder["id"] = admin_user_id(db)

    with_test_db(capture_admin_id)

    admin_reset_response = client.patch(
        f"/api/v1/admin/users/{admin_id_holder['id']}/password",
        headers=auth_headers(admin_token),
        json={"newPassword": "newpass123"},
    )
    assert admin_reset_response.status_code == 400


def test_admin_banner_upload_and_customer_banner_endpoint(client: TestClient) -> None:
    admin_token = create_admin_token(client)

    upload_response = client.post(
        "/api/v1/admin/banners",
        headers=auth_headers(admin_token),
        data={"altText": "Home services banner"},
        files={"image": ("banner.png", b"nearfix-banner", "image/png")},
    )
    assert upload_response.status_code == 201
    banner_id = upload_response.json()["id"]

    def assert_banner_path(db):
        banner = db.query(CustomerHomeBanner).one()
        assert banner.image_path.startswith("banners/customer-banner-")

    with_test_db(assert_banner_path)

    settings_response = client.patch(
        "/api/v1/admin/banner-settings",
        headers=auth_headers(admin_token),
        json={"bannerLimit": 1},
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["bannerLimit"] == 1

    banners_response = client.get("/api/v1/customer/banners")
    assert banners_response.status_code == 200
    assert len(banners_response.json()) == 1
    assert banners_response.json()[0]["id"] == banner_id

    image_response = client.get(f"/api/v1/customer/banners/{banner_id}/image")
    assert image_response.status_code == 200
    assert image_response.content == b"nearfix-banner"

    delete_response = client.delete(
        f"/api/v1/admin/banners/{banner_id}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204

    missing_image_response = client.get(f"/api/v1/customer/banners/{banner_id}/image")
    assert missing_image_response.status_code == 404


def test_public_support_details_returns_defaults(client: TestClient) -> None:
    response = client.get("/api/v1/support-details")

    assert response.status_code == 200
    assert response.json()["footerSiteName"] == "Nearfix.in"
    assert response.json()["adminPhone"] == "7970054811"
    assert response.json()["email"] == "nearfix12132550@gmail.com"
    assert response.json()["helpHeadingEn"] == "Help & Support"


def test_admin_can_update_support_details(client: TestClient) -> None:
    admin_token = create_admin_token(client)
    payload = {
        "footerSiteName": "NearFix Support",
        "adminPhone": "7970054999",
        "email": "support@nearfix.in",
        "helpHeadingEn": "Customer Help",
        "helpHeadingHi": "Madad aur support",
        "helpDescriptionEn": "Call or email NearFix support.",
        "helpDescriptionHi": "NearFix support se sampark karein.",
    }

    update_response = client.patch(
        "/api/v1/admin/support-details",
        headers=auth_headers(admin_token),
        json=payload,
    )
    assert update_response.status_code == 200
    assert update_response.json() == payload

    public_response = client.get("/api/v1/support-details")
    assert public_response.status_code == 200
    assert public_response.json() == payload

    def assert_audit_log(db):
        audit_log = db.query(AdminAuditLog).filter_by(action="support_details_updated").one()
        assert audit_log.target_type == "support_details"

    with_test_db(assert_audit_log)


def test_support_details_validation_rejects_invalid_phone_and_email(client: TestClient) -> None:
    admin_token = create_admin_token(client)
    payload = {
        "footerSiteName": "NearFix Support",
        "adminPhone": "7970054999",
        "email": "support@nearfix.in",
        "helpHeadingEn": "Customer Help",
        "helpHeadingHi": "Madad aur support",
        "helpDescriptionEn": "Call or email NearFix support.",
        "helpDescriptionHi": "NearFix support se sampark karein.",
    }

    invalid_phone_response = client.patch(
        "/api/v1/admin/support-details",
        headers=auth_headers(admin_token),
        json={**payload, "adminPhone": "12345"},
    )
    assert invalid_phone_response.status_code == 422

    invalid_email_response = client.patch(
        "/api/v1/admin/support-details",
        headers=auth_headers(admin_token),
        json={**payload, "email": "not-an-email"},
    )
    assert invalid_email_response.status_code == 422


def test_support_details_update_requires_admin(client: TestClient) -> None:
    customer_token = register_customer(client)
    payload = {
        "footerSiteName": "NearFix Support",
        "adminPhone": "7970054999",
        "email": "support@nearfix.in",
        "helpHeadingEn": "Customer Help",
        "helpHeadingHi": "Madad aur support",
        "helpDescriptionEn": "Call or email NearFix support.",
        "helpDescriptionHi": "NearFix support se sampark karein.",
    }

    unauthenticated_response = client.patch(
        "/api/v1/admin/support-details",
        json=payload,
    )
    assert unauthenticated_response.status_code == 401

    forbidden_response = client.patch(
        "/api/v1/admin/support-details",
        headers=auth_headers(customer_token),
        json=payload,
    )
    assert forbidden_response.status_code == 403


def test_gcs_upload_storage_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeBlob:
        def __init__(self, bucket, name: str) -> None:
            self.bucket = bucket
            self.name = name

        @property
        def content_type(self) -> str | None:
            item = self.bucket.objects.get(self.name)
            return item["content_type"] if item else None

        def upload_from_file(self, file, *, content_type: str) -> None:
            self.bucket.objects[self.name] = {
                "content": file.read(),
                "content_type": content_type,
            }

        def download_as_bytes(self) -> bytes:
            return self.bucket.objects[self.name]["content"]

        def delete(self) -> None:
            self.bucket.objects.pop(self.name, None)

    class FakeBucket:
        def __init__(self) -> None:
            self.objects: dict[str, dict[str, bytes | str]] = {}

        def blob(self, name: str) -> FakeBlob:
            return FakeBlob(self, name)

        def get_blob(self, name: str) -> FakeBlob | None:
            if name not in self.objects:
                return None
            return FakeBlob(self, name)

    class FakeUpload:
        filename = "banner.png"
        content_type = "image/png"

        def __init__(self) -> None:
            self.file = BytesIO(b"gcs-banner")

    fake_bucket = FakeBucket()
    monkeypatch.setattr(settings, "storage_backend", "gcs")
    monkeypatch.setattr(settings, "gcs_bucket_name", "nearfix-test-uploads")
    monkeypatch.setattr(settings, "gcs_upload_prefix", "uploads")
    monkeypatch.setattr(UploadService, "_gcs_bucket", staticmethod(lambda: fake_bucket))

    key = UploadService.save_banner_image(file=FakeUpload())
    assert key.startswith("banners/customer-banner-")
    object_name = f"uploads/{key}"
    assert fake_bucket.objects[object_name]["content"] == b"gcs-banner"

    response = UploadService.file_response(key)
    assert response.body == b"gcs-banner"
    assert response.media_type == "image/png"

    UploadService.delete_file(key)
    assert object_name not in fake_bucket.objects

    with pytest.raises(HTTPException) as exc_info:
        UploadService.file_response(key)
    assert exc_info.value.status_code == 404


def test_admin_added_service_is_available_until_disabled(client: TestClient) -> None:
    admin_token = create_admin_token(client)
    provider_token = register_provider(client)

    create_response = client.post(
        "/api/v1/admin/services",
        headers=auth_headers(admin_token),
        json={"label": "Solar Panel Cleaning", "labelHi": "सोलर पैनल सफाई"},
    )
    assert create_response.status_code == 201
    service = create_response.json()
    assert service["group"] == "Other Services"
    assert service["groupHi"] == "अन्य सेवाएं"
    assert service["labelHi"] == "सोलर पैनल सफाई"
    assert service["slug"] == "solar-panel-cleaning"

    categories_response = client.get("/api/v1/categories")
    assert categories_response.status_code == 200
    categories = categories_response.json()
    assert next(category for category in categories if category["slug"] == "plumber")["labelHi"] == "प्लंबर"
    assert "solar-panel-cleaning" in [category["slug"] for category in categories]
    assert next(category for category in categories if category["slug"] == "solar-panel-cleaning")[
        "labelHi"
    ] == "सोलर पैनल सफाई"

    save_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["solar-panel-cleaning"]},
    )
    assert save_response.status_code == 200

    disable_response = client.patch(
        f"/api/v1/admin/services/{service['id']}",
        headers=auth_headers(admin_token),
        json={"isActive": False},
    )
    assert disable_response.status_code == 200

    hidden_categories_response = client.get("/api/v1/categories")
    assert hidden_categories_response.status_code == 200
    assert "solar-panel-cleaning" not in [
        category["slug"] for category in hidden_categories_response.json()
    ]

    invalid_save_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": ["solar-panel-cleaning"]},
    )
    assert invalid_save_response.status_code == 422


def test_admin_manages_customer_brand_services_and_stores(client: TestClient) -> None:
    admin_token = create_admin_token(client)
    customer_token = register_customer(client)
    provider_token = register_provider(client)
    update_first_provider_status(ProviderVerificationStatus.APPROVED)

    brands_response = client.get("/api/v1/customer/brands")
    assert brands_response.status_code == 200
    brands = brands_response.json()
    assert [brand["name"] for brand in brands].count("Hero & Honda Bike Service") == 1
    assert len(brands) == 4

    admin_brands_response = client.get(
        "/api/v1/admin/brands",
        headers=auth_headers(admin_token),
    )
    assert admin_brands_response.status_code == 200
    samsung_brand = next(
        brand
        for brand in admin_brands_response.json()
        if brand["slug"] == "samsung-service"
    )

    brand_service_response = client.post(
        f"/api/v1/admin/brands/{samsung_brand['id']}/services",
        headers=auth_headers(admin_token),
        json={"categorySlug": "plumber"},
    )
    assert brand_service_response.status_code == 201
    brand_service = brand_service_response.json()
    assert brand_service["categorySlug"] == "plumber"

    manual_store_response = client.post(
        f"/api/v1/admin/brand-services/{brand_service['id']}/stores/manual",
        headers=auth_headers(admin_token),
        json={
            "shopName": "Samsung Manual Store",
            "contactName": "Manual Owner",
            "phone": "7970054833",
            "email": "manual@example.com",
            "latitude": 20.5937,
            "longitude": 78.9629,
        },
    )
    assert manual_store_response.status_code == 201
    assert manual_store_response.json()["storeType"] == "manual"

    provider_profile_response = client.get(
        "/api/v1/provider/me",
        headers=auth_headers(provider_token),
    )
    assert provider_profile_response.status_code == 200
    provider_id = provider_profile_response.json()["id"]

    provider_store_response = client.post(
        f"/api/v1/admin/brand-services/{brand_service['id']}/stores/provider",
        headers=auth_headers(admin_token),
        json={"providerProfileId": provider_id},
    )
    assert provider_store_response.status_code == 201
    provider_store = provider_store_response.json()
    assert provider_store["storeType"] == "provider"
    assert provider_store["providerProfileId"] == provider_id

    provider_categories_response = client.get(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
    )
    assert provider_categories_response.status_code == 200
    assert "plumber" in provider_categories_response.json()["categorySlugs"]

    services_response = client.get("/api/v1/customer/brands/samsung-service/services")
    assert services_response.status_code == 200
    assert [service["categorySlug"] for service in services_response.json()] == ["plumber"]

    stores_response = client.get(
        "/api/v1/customer/brands/samsung-service/services/plumber/stores",
        headers=auth_headers(customer_token),
        params={"lat": 20.5937, "lng": 78.9629},
    )
    assert stores_response.status_code == 200
    stores = stores_response.json()
    assert {store["storeType"] for store in stores} == {"manual", "provider"}
    assert next(store for store in stores if store["storeType"] == "manual")[
        "providerProfileId"
    ] is None

    booking_response = client.post(
        "/api/v1/customer/bookings",
        headers=auth_headers(customer_token),
        json={
            "providerProfileId": provider_id,
            "categorySlug": "plumber",
            "latitude": 20.5937,
            "longitude": 78.9629,
        },
    )
    assert booking_response.status_code == 201

    disable_store_response = client.patch(
        f"/api/v1/admin/brand-stores/{provider_store['id']}",
        headers=auth_headers(admin_token),
        json={"isActive": False},
    )
    assert disable_store_response.status_code == 200

    visible_stores_response = client.get(
        "/api/v1/customer/brands/samsung-service/services/plumber/stores",
        headers=auth_headers(customer_token),
    )
    assert visible_stores_response.status_code == 200
    assert [store["storeType"] for store in visible_stores_response.json()] == ["manual"]

    disable_service_response = client.patch(
        f"/api/v1/admin/brand-services/{brand_service['id']}",
        headers=auth_headers(admin_token),
        json={"isActive": False},
    )
    assert disable_service_response.status_code == 200

    hidden_services_response = client.get("/api/v1/customer/brands/samsung-service/services")
    assert hidden_services_response.status_code == 200
    assert hidden_services_response.json() == []

    def assert_booking_saved(db):
        assert db.query(Booking).filter_by(category_slug="plumber").count() == 1
        audit_actions = {audit_log.action for audit_log in db.query(AdminAuditLog).all()}
        assert "brand_service_created" in audit_actions
        assert "brand_store_manual_created" in audit_actions
        assert "brand_store_provider_created" in audit_actions

    with_test_db(assert_booking_saved)


def test_admin_can_delete_unused_custom_service(client: TestClient) -> None:
    admin_token = create_admin_token(client)
    provider_token = register_provider(client)

    create_response = client.post(
        "/api/v1/admin/services",
        headers=auth_headers(admin_token),
        json={"label": "Window Cleaning QA", "labelHi": "Window Cleaning Hindi"},
    )
    assert create_response.status_code == 201
    service = create_response.json()
    assert service["slug"] == "window-cleaning-qa"

    save_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": [service["slug"]]},
    )
    assert save_response.status_code == 200

    delete_response = client.delete(
        f"/api/v1/admin/services/{service['id']}",
        headers=auth_headers(admin_token),
    )
    assert delete_response.status_code == 204

    categories_response = client.get("/api/v1/categories")
    assert categories_response.status_code == 200
    assert service["slug"] not in [
        category["slug"] for category in categories_response.json()
    ]

    admin_services_response = client.get(
        "/api/v1/admin/services",
        headers=auth_headers(admin_token),
    )
    assert admin_services_response.status_code == 200
    assert service["slug"] not in [
        category["slug"] for category in admin_services_response.json()
    ]

    provider_categories_response = client.get(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
    )
    assert provider_categories_response.status_code == 200
    assert provider_categories_response.json()["categorySlugs"] == []

    def assert_audit_log(db):
        audit_log = db.query(AdminAuditLog).filter_by(action="service_deleted").one()
        assert audit_log.target_type == "service_category"
        assert audit_log.target_id == str(service["id"])
        assert service["slug"] in (audit_log.metadata_json or "")

    with_test_db(assert_audit_log)


def test_admin_cannot_delete_default_service(client: TestClient) -> None:
    admin_token = create_admin_token(client)

    services_response = client.get(
        "/api/v1/admin/services",
        headers=auth_headers(admin_token),
    )
    assert services_response.status_code == 200
    plumber = next(
        service for service in services_response.json() if service["slug"] == "plumber"
    )

    delete_response = client.delete(
        f"/api/v1/admin/services/{plumber['id']}",
        headers=auth_headers(admin_token),
    )

    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "Default services cannot be deleted"


def test_admin_cannot_delete_custom_service_with_bookings(client: TestClient) -> None:
    admin_token = create_admin_token(client)
    provider_token = register_provider(client)
    customer_token = register_customer(client)

    create_response = client.post(
        "/api/v1/admin/services",
        headers=auth_headers(admin_token),
        json={"label": "Booked Cleaning QA", "labelHi": "Booked Cleaning Hindi"},
    )
    assert create_response.status_code == 201
    service = create_response.json()

    save_response = client.put(
        "/api/v1/provider/categories",
        headers=auth_headers(provider_token),
        json={"categorySlugs": [service["slug"]]},
    )
    assert save_response.status_code == 200

    update_first_provider_status(ProviderVerificationStatus.APPROVED)

    provider_profile_response = client.get(
        "/api/v1/provider/me",
        headers=auth_headers(provider_token),
    )
    assert provider_profile_response.status_code == 200
    provider_id = provider_profile_response.json()["id"]

    booking_response = client.post(
        "/api/v1/customer/bookings",
        headers=auth_headers(customer_token),
        json={
            "providerProfileId": provider_id,
            "categorySlug": service["slug"],
            "latitude": 20.5937,
            "longitude": 78.9629,
        },
    )
    assert booking_response.status_code == 201

    def assert_booking_saved(db):
        assert db.query(Booking).filter_by(category_slug=service["slug"]).count() == 1

    with_test_db(assert_booking_saved)

    delete_response = client.delete(
        f"/api/v1/admin/services/{service['id']}",
        headers=auth_headers(admin_token),
    )

    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "Service has bookings. Disable it instead."
