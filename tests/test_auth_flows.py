from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.provider_document_change_request import ProviderDocumentChangeRequest
from app.models.provider_profile import ProviderProfile, ProviderVerificationStatus
from app.models.user import User, UserRole
from app.models.user_phone_history import UserPhoneHistory


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
