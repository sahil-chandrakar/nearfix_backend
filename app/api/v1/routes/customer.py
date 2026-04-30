from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import CustomerUser, DBSession
from app.core.security import create_access_token
from app.models.user import UserRole
from app.repositories.banner_repository import BannerRepository
from app.schemas.auth import Token
from app.schemas.banner import BannerRead
from app.schemas.booking import BookingCreate, BookingRead
from app.schemas.category import CustomerProviderSearchResult
from app.schemas.customer import (
    CustomerProfileUpdate,
    CustomerRegisterRequest,
    PhoneLoginRequest,
)
from app.schemas.user import UserRead
from app.services.auth_service import AuthService
from app.services.booking_notifier import provider_booking_notifier
from app.services.booking_service import BookingService
from app.services.category_service import CategoryService
from app.services.upload_service import UploadService

router = APIRouter(prefix="/customer", tags=["customer"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
def register_customer(payload: CustomerRegisterRequest, db: DBSession) -> Token:
    user = AuthService.register_customer(db=db, payload=payload)
    return Token(access_token=create_access_token(subject=user.id))


@router.post("/login", response_model=Token)
def login_customer(payload: PhoneLoginRequest, db: DBSession) -> Token:
    user = AuthService.authenticate_phone(
        db=db,
        phone=payload.phone,
        password=payload.password,
        expected_role=UserRole.CUSTOMER,
    )
    return Token(access_token=create_access_token(subject=user.id))


@router.get("/me", response_model=UserRead)
def read_customer(current_user: CustomerUser) -> UserRead:
    return current_user


@router.get("/banners", response_model=list[BannerRead])
def read_customer_banners(db: DBSession) -> list[BannerRead]:
    return [
        BannerRead(
            id=banner.id,
            image_url=f"/api/v1/customer/banners/{banner.id}/image",
            alt_text=banner.alt_text,
            display_order=banner.display_order,
            is_active=banner.is_active,
            created_at=banner.created_at,
            updated_at=banner.updated_at,
        )
        for banner in BannerRepository.list_active_for_customer(db)
    ]


@router.get("/banners/{banner_id}/image")
def read_customer_banner_image(banner_id: int, db: DBSession) -> FileResponse:
    banner = BannerRepository.get_by_id(db, banner_id=banner_id)
    if banner is None or not banner.is_active:
        raise HTTPException(status_code=404, detail="Banner not found")
    return FileResponse(UploadService.resolve_safe_upload_path(banner.image_path))


@router.patch("/me", response_model=UserRead)
def update_customer_profile(
    payload: CustomerProfileUpdate,
    current_user: CustomerUser,
    db: DBSession,
) -> UserRead:
    return AuthService.update_customer_profile(
        db,
        user=current_user,
        payload=payload,
    )


@router.post(
    "/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_booking(
    payload: BookingCreate,
    current_user: CustomerUser,
    db: DBSession,
) -> BookingRead:
    booking = BookingService.create_customer_booking(
        db,
        customer=current_user,
        payload=payload,
    )
    await provider_booking_notifier.notify_booking_created(
        provider_profile_id=booking.provider_profile_id,
        booking=booking,
    )
    return booking


@router.get("/bookings", response_model=list[BookingRead])
def read_customer_bookings(
    current_user: CustomerUser,
    db: DBSession,
) -> list[BookingRead]:
    return BookingService.list_customer_bookings(db, customer=current_user)


@router.get("/providers", response_model=list[CustomerProviderSearchResult])
def search_customer_providers(
    category: str,
    current_user: CustomerUser,
    db: DBSession,
    lat: float | None = None,
    lng: float | None = None,
) -> list[CustomerProviderSearchResult]:
    return CategoryService.search_customer_providers(
        db,
        category_slug=category,
        latitude=lat,
        longitude=lng,
    )
