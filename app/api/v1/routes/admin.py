from typing import Annotated
import re

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.api.deps import AdminUser, DBSession
from app.core.security import create_access_token
from app.models.booking import Booking, BookingStatus
from app.models.customer_home_banner import CustomerHomeBanner
from app.models.provider_document_change_request import (
    ProviderDocumentChangeRequest,
    ProviderDocumentChangeStatus,
    ProviderDocumentType,
)
from app.models.provider_profile import ProviderProfile, ProviderVerificationStatus
from app.models.service_category import ServiceCategory
from app.models.user import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.banner_repository import BannerRepository
from app.repositories.booking_repository import BookingRepository
from app.repositories.provider_document_repository import ProviderDocumentRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.service_category_repository import ServiceCategoryRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminAuditLogRead,
    AdminBookingRead,
    AdminCustomerPhoneHistoryRead,
    AdminCustomerRead,
    AdminLoginRequest,
    AdminProviderRead,
    AdminSummary,
    UserActiveUpdate,
)
from app.schemas.auth import Token
from app.schemas.banner import BannerRead, BannerSettingsRead, BannerSettingsUpdate, BannerUpdate
from app.schemas.category import ServiceCategoryCreate, ServiceCategoryRead, ServiceCategoryUpdate
from app.schemas.provider import ProviderVerificationUpdate
from app.schemas.provider_document import (
    ProviderDocumentChangeRead,
    ProviderDocumentChangeReview,
)
from app.services.auth_service import AuthService
from app.services.booking_service import BookingService
from app.services.provider_service import ProviderService
from app.services.upload_service import UploadService

router = APIRouter(prefix="/admin", tags=["admin"])


def _count(db: DBSession, statement) -> int:
    return int(db.scalar(statement) or 0)


def _provider_to_read(db: DBSession, provider: ProviderProfile) -> AdminProviderRead:
    return AdminProviderRead(
        id=provider.id,
        user_id=provider.user_id,
        shop_company_name=provider.shop_company_name,
        owner_name=provider.owner_name,
        whatsapp_mobile_number=provider.whatsapp_mobile_number,
        email=provider.email,
        aadhaar_front_path=provider.aadhaar_front_path,
        aadhaar_back_path=provider.aadhaar_back_path,
        payment_bill_path=provider.payment_bill_path,
        electricity_bill_path=provider.electricity_bill_path,
        latitude=provider.latitude,
        longitude=provider.longitude,
        verification_status=provider.verification_status,
        rejection_reason=provider.rejection_reason,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        category_slugs=ProviderRepository.get_category_slugs(
            db,
            provider_profile_id=provider.id,
        ),
        user_is_active=provider.user.is_active if provider.user else True,
    )


def _banner_to_read(banner: CustomerHomeBanner) -> BannerRead:
    return BannerRead(
        id=banner.id,
        image_url=f"/api/v1/admin/banners/{banner.id}/image",
        alt_text=banner.alt_text,
        display_order=banner.display_order,
        is_active=banner.is_active,
        created_at=banner.created_at,
        updated_at=banner.updated_at,
    )


def _category_to_read(category: ServiceCategory) -> ServiceCategoryRead:
    return ServiceCategoryRead(
        id=category.id,
        slug=category.slug,
        label=category.label,
        group=category.group,
        is_active=category.is_active,
        display_order=category.display_order,
    )


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")
    return slug or "service"


def _unique_service_slug(db: DBSession, label: str) -> str:
    base_slug = _slugify(label)
    slug = base_slug
    suffix = 2
    while ServiceCategoryRepository.get_by_slug(db, slug=slug, active_only=False) is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


@router.post("/login", response_model=Token)
def login_admin(payload: AdminLoginRequest, db: DBSession) -> Token:
    user = AuthService.authenticate_phone(
        db=db,
        phone=payload.phone,
        password=payload.password,
        expected_role=UserRole.ADMIN,
    )
    return Token(access_token=create_access_token(subject=user.id))


@router.get("/summary", response_model=AdminSummary)
def read_admin_summary(_current_user: AdminUser, db: DBSession) -> AdminSummary:
    ServiceCategoryRepository.ensure_seeded(db)
    return AdminSummary(
        total_customers=_count(db, select(func.count()).select_from(User).where(User.role == UserRole.CUSTOMER.value)),
        total_providers=_count(db, select(func.count()).select_from(User).where(User.role == UserRole.PROVIDER.value)),
        pending_providers=_count(
            db,
            select(func.count()).select_from(ProviderProfile).where(
                ProviderProfile.verification_status == ProviderVerificationStatus.PENDING.value
            ),
        ),
        approved_providers=_count(
            db,
            select(func.count()).select_from(ProviderProfile).where(
                ProviderProfile.verification_status == ProviderVerificationStatus.APPROVED.value
            ),
        ),
        rejected_providers=_count(
            db,
            select(func.count()).select_from(ProviderProfile).where(
                ProviderProfile.verification_status == ProviderVerificationStatus.REJECTED.value
            ),
        ),
        pending_document_requests=_count(
            db,
            select(func.count()).select_from(ProviderDocumentChangeRequest).where(
                ProviderDocumentChangeRequest.status == ProviderDocumentChangeStatus.PENDING.value
            ),
        ),
        total_bookings=_count(db, select(func.count()).select_from(Booking)),
        pending_bookings=_count(
            db,
            select(func.count()).select_from(Booking).where(Booking.status == BookingStatus.PENDING.value),
        ),
        accepted_bookings=_count(
            db,
            select(func.count()).select_from(Booking).where(Booking.status == BookingStatus.ACCEPTED.value),
        ),
        declined_bookings=_count(
            db,
            select(func.count()).select_from(Booking).where(Booking.status == BookingStatus.DECLINED.value),
        ),
        active_banners=_count(
            db,
            select(func.count()).select_from(CustomerHomeBanner).where(CustomerHomeBanner.is_active.is_(True)),
        ),
        active_services=_count(
            db,
            select(func.count()).select_from(ServiceCategory).where(ServiceCategory.is_active.is_(True)),
        ),
    )


@router.get("/providers", response_model=list[AdminProviderRead])
def list_providers(
    _current_user: AdminUser,
    db: DBSession,
    verification_status: Annotated[
        ProviderVerificationStatus | None,
        Query(alias="status"),
    ] = None,
    q: str | None = None,
    category: str | None = None,
) -> list[AdminProviderRead]:
    return [
        _provider_to_read(db, provider)
        for provider in ProviderRepository.list_all(
            db,
            verification_status=verification_status,
            q=q,
            category_slug=category,
        )
    ]


@router.get("/providers/pending", response_model=list[AdminProviderRead])
def list_pending_providers(
    _current_user: AdminUser,
    db: DBSession,
) -> list[AdminProviderRead]:
    return [_provider_to_read(db, provider) for provider in ProviderRepository.list_pending(db)]


@router.get("/providers/{provider_id}", response_model=AdminProviderRead)
def read_provider(provider_id: int, _current_user: AdminUser, db: DBSession) -> AdminProviderRead:
    profile = ProviderRepository.get_by_id(db, provider_id=provider_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return _provider_to_read(db, profile)


@router.patch(
    "/providers/{provider_id}/verification-status",
    response_model=AdminProviderRead,
)
def update_provider_verification_status(
    provider_id: int,
    payload: ProviderVerificationUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> AdminProviderRead:
    profile = ProviderRepository.get_by_id(db, provider_id=provider_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider profile not found",
        )

    updated = ProviderRepository.update_verification_status(
        db,
        profile=profile,
        verification_status=payload.verification_status,
        rejection_reason=payload.reason,
    )
    AuditRepository.create(
        db,
        admin_user=current_user,
        action=f"provider_{payload.verification_status.value}",
        target_type="provider",
        target_id=provider_id,
        metadata={"reason": payload.reason},
    )
    return _provider_to_read(db, updated)


@router.get("/providers/{provider_id}/documents/{document_type}")
def read_provider_document(
    provider_id: int,
    document_type: ProviderDocumentType,
    _current_user: AdminUser,
    db: DBSession,
) -> FileResponse:
    profile = ProviderRepository.get_by_id(db, provider_id=provider_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    document_path_by_type = {
        ProviderDocumentType.AADHAAR_FRONT: profile.aadhaar_front_path,
        ProviderDocumentType.AADHAAR_BACK: profile.aadhaar_back_path,
        ProviderDocumentType.PAYMENT_BILL: profile.payment_bill_path,
        ProviderDocumentType.ELECTRICITY_BILL: profile.electricity_bill_path,
    }
    return FileResponse(
        UploadService.resolve_safe_upload_path(document_path_by_type[document_type])
    )


@router.get(
    "/provider-document-change-requests",
    response_model=list[ProviderDocumentChangeRead],
)
def list_provider_document_change_requests(
    _current_user: AdminUser,
    db: DBSession,
    request_status: Annotated[
        ProviderDocumentChangeStatus | None,
        Query(alias="status"),
    ] = None,
) -> list[ProviderDocumentChangeRead]:
    return ProviderDocumentRepository.list_by_status(db, status=request_status)


@router.get(
    "/provider-document-change-requests/pending",
    response_model=list[ProviderDocumentChangeRead],
)
def list_pending_provider_document_change_requests(
    _current_user: AdminUser,
    db: DBSession,
) -> list[ProviderDocumentChangeRead]:
    return ProviderService.list_pending_document_requests(db)


@router.patch(
    "/provider-document-change-requests/{request_id}",
    response_model=ProviderDocumentChangeRead,
)
def review_provider_document_change_request(
    request_id: int,
    payload: ProviderDocumentChangeReview,
    current_user: AdminUser,
    db: DBSession,
) -> ProviderDocumentChangeRead:
    reviewed = ProviderService.review_document_request(
        db,
        request_id=request_id,
        review_status=payload.status,
        admin_user=current_user,
        reason=payload.reason,
    )
    AuditRepository.create(
        db,
        admin_user=current_user,
        action=f"document_{payload.status.value}",
        target_type="provider_document_change_request",
        target_id=request_id,
        metadata={"reason": payload.reason, "documentType": reviewed.document_type},
    )
    return reviewed


@router.get("/provider-document-change-requests/{request_id}/file")
def read_provider_document_change_file(
    request_id: int,
    _current_user: AdminUser,
    db: DBSession,
) -> FileResponse:
    request = ProviderDocumentRepository.get_by_id(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document request not found")
    return FileResponse(UploadService.resolve_safe_upload_path(request.document_path))


@router.get("/customers", response_model=list[AdminCustomerRead])
def list_customers(
    _current_user: AdminUser,
    db: DBSession,
    q: str | None = None,
) -> list[AdminCustomerRead]:
    customers = UserRepository.list_by_role(db, role=UserRole.CUSTOMER, q=q)
    return [
        AdminCustomerRead(
            id=customer.id,
            email=customer.email,
            phone=customer.phone,
            full_name=customer.full_name,
            role=customer.role,
            is_active=customer.is_active,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            phone_history=[
                AdminCustomerPhoneHistoryRead.model_validate(row)
                for row in UserRepository.list_phone_history(db, user_id=customer.id)
            ],
        )
        for customer in customers
    ]


@router.get("/bookings", response_model=list[AdminBookingRead])
def list_bookings(
    _current_user: AdminUser,
    db: DBSession,
    booking_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    category: str | None = None,
    q: str | None = None,
) -> list[AdminBookingRead]:
    return [
        AdminBookingRead.model_validate(BookingService.to_read(db, booking))
        for booking in BookingRepository.list_all(
            db,
            status=booking_status,
            category_slug=category,
            q=q,
        )
    ]


@router.patch("/users/{user_id}/active", response_model=AdminCustomerRead)
def update_user_active(
    user_id: int,
    payload: UserActiveUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> AdminCustomerRead:
    user = UserRepository.get_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin users cannot be changed here")
    updated = UserRepository.update_active(db, user=user, is_active=payload.is_active)
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="user_activated" if payload.is_active else "user_deactivated",
        target_type="user",
        target_id=user_id,
    )
    return AdminCustomerRead(
        id=updated.id,
        email=updated.email,
        phone=updated.phone,
        full_name=updated.full_name,
        role=updated.role,
        is_active=updated.is_active,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        phone_history=[
            AdminCustomerPhoneHistoryRead.model_validate(row)
            for row in UserRepository.list_phone_history(db, user_id=updated.id)
        ],
    )


@router.get("/audit-logs", response_model=list[AdminAuditLogRead])
def list_audit_logs(_current_user: AdminUser, db: DBSession) -> list[AdminAuditLogRead]:
    return AuditRepository.list_recent(db)


@router.get("/banners", response_model=list[BannerRead])
def list_banners(_current_user: AdminUser, db: DBSession) -> list[BannerRead]:
    return [_banner_to_read(banner) for banner in BannerRepository.list_banners(db)]


@router.post("/banners", response_model=BannerRead, status_code=status.HTTP_201_CREATED)
def create_banner(
    current_user: AdminUser,
    db: DBSession,
    image: Annotated[UploadFile, File()],
    alt_text: Annotated[str, Form(alias="altText", min_length=1, max_length=255)] = "NearFix banner",
    display_order: Annotated[int | None, Form(alias="displayOrder", ge=0)] = None,
) -> BannerRead:
    image_path = UploadService.save_banner_image(file=image)
    banner = BannerRepository.create(
        db,
        image_path=image_path,
        alt_text=alt_text,
        display_order=display_order if display_order is not None else BannerRepository.next_display_order(db),
    )
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="banner_created",
        target_type="banner",
        target_id=banner.id,
    )
    return _banner_to_read(banner)


@router.patch("/banners/{banner_id}", response_model=BannerRead)
def update_banner(
    banner_id: int,
    payload: BannerUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> BannerRead:
    banner = BannerRepository.get_by_id(db, banner_id=banner_id)
    if banner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    updated = BannerRepository.update(
        db,
        banner=banner,
        alt_text=payload.alt_text,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="banner_updated",
        target_type="banner",
        target_id=banner_id,
        metadata=payload.model_dump(exclude_none=True),
    )
    return _banner_to_read(updated)


@router.delete("/banners/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_banner(banner_id: int, current_user: AdminUser, db: DBSession) -> None:
    banner = BannerRepository.get_by_id(db, banner_id=banner_id)
    if banner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    BannerRepository.delete(db, banner=banner)
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="banner_deleted",
        target_type="banner",
        target_id=banner_id,
    )


@router.get("/banners/{banner_id}/image")
def read_admin_banner_image(
    banner_id: int,
    _current_user: AdminUser,
    db: DBSession,
) -> FileResponse:
    banner = BannerRepository.get_by_id(db, banner_id=banner_id)
    if banner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    return FileResponse(UploadService.resolve_safe_upload_path(banner.image_path))


@router.get("/banner-settings", response_model=BannerSettingsRead)
def read_banner_settings(_current_user: AdminUser, db: DBSession) -> BannerSettingsRead:
    return BannerSettingsRead(banner_limit=BannerRepository.get_banner_limit(db))


@router.patch("/banner-settings", response_model=BannerSettingsRead)
def update_banner_settings(
    payload: BannerSettingsUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> BannerSettingsRead:
    banner_limit = BannerRepository.set_banner_limit(db, banner_limit=payload.banner_limit)
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="banner_settings_updated",
        target_type="banner_settings",
        metadata={"bannerLimit": banner_limit},
    )
    return BannerSettingsRead(banner_limit=banner_limit)


@router.get("/services", response_model=list[ServiceCategoryRead])
def list_services(_current_user: AdminUser, db: DBSession) -> list[ServiceCategoryRead]:
    return [
        _category_to_read(category)
        for category in ServiceCategoryRepository.list_categories(db, active_only=False)
    ]


@router.post("/services", response_model=ServiceCategoryRead, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCategoryCreate,
    current_user: AdminUser,
    db: DBSession,
) -> ServiceCategoryRead:
    label = payload.label.strip()
    if len(label) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Service label is too short")
    category = ServiceCategoryRepository.create(
        db,
        slug=_unique_service_slug(db, label),
        label=label,
        group="Other Services",
        display_order=ServiceCategoryRepository.next_display_order(db, group="Other Services"),
    )
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="service_created",
        target_type="service_category",
        target_id=category.id,
        metadata={"slug": category.slug, "label": category.label},
    )
    return _category_to_read(category)


@router.patch("/services/{service_id}", response_model=ServiceCategoryRead)
def update_service(
    service_id: int,
    payload: ServiceCategoryUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> ServiceCategoryRead:
    category = ServiceCategoryRepository.get_by_id(db, category_id=service_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    label = payload.label.strip() if payload.label is not None else None
    if label is not None and len(label) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Service label is too short")
    updated = ServiceCategoryRepository.update(
        db,
        category=category,
        label=label,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    AuditRepository.create(
        db,
        admin_user=current_user,
        action="service_updated",
        target_type="service_category",
        target_id=service_id,
        metadata=payload.model_dump(exclude_none=True),
    )
    return _category_to_read(updated)
