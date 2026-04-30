from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.booking import Booking, BookingStatus
from app.models.provider_profile import ProviderProfile
from app.models.user import User


class BookingRepository:
    @staticmethod
    def get_by_id(db: Session, booking_id: int) -> Booking | None:
        return db.scalar(
            select(Booking)
            .options(joinedload(Booking.customer), joinedload(Booking.provider_profile))
            .where(Booking.id == booking_id)
        )

    @staticmethod
    def get_pending_duplicate(
        db: Session,
        *,
        customer_id: int,
        provider_profile_id: int,
        category_slug: str,
    ) -> Booking | None:
        return db.scalar(
            select(Booking)
            .where(
                Booking.customer_id == customer_id,
                Booking.provider_profile_id == provider_profile_id,
                Booking.category_slug == category_slug,
                Booking.status == BookingStatus.PENDING.value,
            )
            .order_by(Booking.created_at.desc(), Booking.id.desc())
        )

    @staticmethod
    def create(
        db: Session,
        *,
        customer_id: int,
        provider_profile_id: int,
        category_slug: str,
        latitude: float | None,
        longitude: float | None,
    ) -> Booking:
        booking = Booking(
            customer_id=customer_id,
            provider_profile_id=provider_profile_id,
            category_slug=category_slug,
            customer_latitude=latitude,
            customer_longitude=longitude,
            status=BookingStatus.PENDING.value,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking

    @staticmethod
    def list_for_customer(db: Session, *, customer_id: int) -> list[Booking]:
        return list(
            db.scalars(
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.provider_profile))
                .where(Booking.customer_id == customer_id)
                .order_by(Booking.created_at.desc(), Booking.id.desc())
            )
        )

    @staticmethod
    def list_for_provider(
        db: Session,
        *,
        provider_profile_id: int,
        status: BookingStatus,
    ) -> list[Booking]:
        return list(
            db.scalars(
                select(Booking)
                .options(joinedload(Booking.customer), joinedload(Booking.provider_profile))
                .where(
                    Booking.provider_profile_id == provider_profile_id,
                    Booking.status == status.value,
                )
                .order_by(Booking.created_at.desc(), Booking.id.desc())
            )
        )

    @staticmethod
    def list_all(
        db: Session,
        *,
        status: BookingStatus | None = None,
        category_slug: str | None = None,
        q: str | None = None,
    ) -> list[Booking]:
        statement = (
            select(Booking)
            .join(User, User.id == Booking.customer_id)
            .join(ProviderProfile, ProviderProfile.id == Booking.provider_profile_id)
            .options(joinedload(Booking.customer), joinedload(Booking.provider_profile))
        )
        if status is not None:
            statement = statement.where(Booking.status == status.value)
        if category_slug:
            statement = statement.where(Booking.category_slug == category_slug)
        if q:
            like = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    User.phone.ilike(like),
                    User.full_name.ilike(like),
                    ProviderProfile.shop_company_name.ilike(like),
                    ProviderProfile.owner_name.ilike(like),
                    ProviderProfile.whatsapp_mobile_number.ilike(like),
                )
            )
        return list(
            db.scalars(statement.order_by(Booking.created_at.desc(), Booking.id.desc()))
        )

    @staticmethod
    def update_status(db: Session, *, booking: Booking, status: BookingStatus) -> Booking:
        booking.status = status.value
        if status == BookingStatus.ACCEPTED:
            booking.accepted_at = datetime.now(timezone.utc)
            booking.declined_at = None
        if status == BookingStatus.DECLINED:
            booking.declined_at = datetime.now(timezone.utc)
            booking.accepted_at = None
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
