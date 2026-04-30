from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.models.provider_profile import ProviderVerificationStatus
from app.models.user import User
from app.repositories.booking_repository import BookingRepository
from app.repositories.provider_repository import ProviderRepository
from app.schemas.booking import BookingCreate, BookingRead
from app.services.category_service import CategoryService


class BookingService:
    @staticmethod
    def create_customer_booking(
        db: Session,
        *,
        customer: User,
        payload: BookingCreate,
    ) -> BookingRead:
        CategoryService.validate_category_slugs(db, [payload.category_slug])
        provider = ProviderRepository.get_by_id(
            db,
            provider_id=payload.provider_profile_id,
        )
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found",
            )
        if provider.verification_status != ProviderVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider is not approved yet",
            )

        provider_category_slugs = ProviderRepository.get_category_slugs(
            db,
            provider_profile_id=provider.id,
        )
        if payload.category_slug not in provider_category_slugs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider does not offer this service",
            )

        booking = BookingRepository.get_pending_duplicate(
            db,
            customer_id=customer.id,
            provider_profile_id=provider.id,
            category_slug=payload.category_slug,
        )
        if booking is None:
            booking = BookingRepository.create(
                db,
                customer_id=customer.id,
                provider_profile_id=provider.id,
                category_slug=payload.category_slug,
                latitude=payload.latitude,
                longitude=payload.longitude,
            )
        else:
            booking.customer_latitude = payload.latitude
            booking.customer_longitude = payload.longitude
            db.add(booking)
            db.commit()
            db.refresh(booking)

        booking.customer = customer
        booking.provider_profile = provider
        return BookingService.to_read(db, booking)

    @staticmethod
    def list_customer_bookings(db: Session, *, customer: User) -> list[BookingRead]:
        return [
            BookingService.to_read(db, booking)
            for booking in BookingRepository.list_for_customer(
                db,
                customer_id=customer.id,
            )
        ]

    @staticmethod
    def list_provider_bookings(
        db: Session,
        *,
        provider_user: User,
        booking_status: BookingStatus,
    ) -> list[BookingRead]:
        profile = ProviderRepository.get_by_user_id(db, user_id=provider_user.id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found",
            )

        return [
            BookingService.to_read(db, booking)
            for booking in BookingRepository.list_for_provider(
                db,
                provider_profile_id=profile.id,
                status=booking_status,
            )
        ]

    @staticmethod
    def update_provider_booking_status(
        db: Session,
        *,
        provider_user: User,
        booking_id: int,
        booking_status: BookingStatus,
    ) -> BookingRead:
        profile = ProviderRepository.get_by_user_id(db, user_id=provider_user.id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found",
            )

        booking = BookingRepository.get_by_id(db, booking_id)
        if booking is None or booking.provider_profile_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found",
            )
        if booking_status not in {BookingStatus.ACCEPTED, BookingStatus.DECLINED}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Unsupported booking status",
            )

        return BookingService.to_read(
            db,
            BookingRepository.update_status(
                db,
                booking=booking,
                status=booking_status,
            )
        )

    @staticmethod
    def to_read(db: Session, booking: Booking) -> BookingRead:
        provider = booking.provider_profile
        distance_km = None
        if (
            booking.customer_latitude is not None
            and booking.customer_longitude is not None
            and provider.latitude is not None
            and provider.longitude is not None
        ):
            distance_km = round(
                CategoryService._distance_km(
                    booking.customer_latitude,
                    booking.customer_longitude,
                    provider.latitude,
                    provider.longitude,
                ),
                1,
            )

        return BookingRead(
            id=booking.id,
            customer_id=booking.customer_id,
            provider_profile_id=booking.provider_profile_id,
            category_slug=booking.category_slug,
            service_label=CategoryService.get_category_label(
                db,
                category_slug=booking.category_slug,
            ),
            status=booking.status,
            customer_phone=booking.customer.phone,
            customer_name=booking.customer.full_name,
            provider_phone=provider.whatsapp_mobile_number,
            shop_company_name=provider.shop_company_name,
            owner_name=provider.owner_name,
            distance_km=distance_km,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
            accepted_at=booking.accepted_at,
            declined_at=booking.declined_at,
        )
