from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.provider_category import ProviderCategory
from app.models.provider_profile import ProviderProfile, ProviderVerificationStatus
from app.models.user import User
from app.models.user_phone_history import UserPhoneHistory


class ProviderRepository:
    @staticmethod
    def get_by_id(db: Session, provider_id: int) -> ProviderProfile | None:
        return db.scalar(select(ProviderProfile).where(ProviderProfile.id == provider_id))

    @staticmethod
    def get_by_user_id(db: Session, user_id: int) -> ProviderProfile | None:
        return db.scalar(select(ProviderProfile).where(ProviderProfile.user_id == user_id))

    @staticmethod
    def list_pending(db: Session) -> list[ProviderProfile]:
        return list(
            db.scalars(
                select(ProviderProfile).where(
                    ProviderProfile.verification_status
                    == ProviderVerificationStatus.PENDING.value,
                )
            )
        )

    @staticmethod
    def list_all(
        db: Session,
        *,
        verification_status: ProviderVerificationStatus | None = None,
        q: str | None = None,
        category_slug: str | None = None,
    ) -> list[ProviderProfile]:
        statement = select(ProviderProfile)
        if category_slug:
            statement = statement.join(
                ProviderCategory,
                ProviderCategory.provider_profile_id == ProviderProfile.id,
            ).where(ProviderCategory.category_slug == category_slug)
        if verification_status is not None:
            statement = statement.where(
                ProviderProfile.verification_status == verification_status.value
            )
        if q:
            like = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    ProviderProfile.shop_company_name.ilike(like),
                    ProviderProfile.owner_name.ilike(like),
                    ProviderProfile.whatsapp_mobile_number.ilike(like),
                    ProviderProfile.email.ilike(like),
                )
            )
        return list(
            db.scalars(
                statement.order_by(
                    ProviderProfile.created_at.desc(),
                    ProviderProfile.id.desc(),
                ).distinct()
            )
        )

    @staticmethod
    def list_approved_by_category(
        db: Session,
        *,
        category_slug: str,
    ) -> list[ProviderProfile]:
        return list(
            db.scalars(
                select(ProviderProfile)
                .join(
                    ProviderCategory,
                    ProviderCategory.provider_profile_id == ProviderProfile.id,
                )
                .where(
                    ProviderProfile.verification_status
                    == ProviderVerificationStatus.APPROVED.value,
                    ProviderCategory.category_slug == category_slug,
                )
                .order_by(ProviderProfile.shop_company_name)
            )
        )

    @staticmethod
    def get_category_slugs(
        db: Session,
        *,
        provider_profile_id: int,
    ) -> list[str]:
        return list(
            db.scalars(
                select(ProviderCategory.category_slug)
                .where(ProviderCategory.provider_profile_id == provider_profile_id)
                .order_by(ProviderCategory.category_slug)
            )
        )

    @staticmethod
    def set_category_slugs(
        db: Session,
        *,
        provider_profile_id: int,
        category_slugs: list[str],
    ) -> list[str]:
        db.execute(
            delete(ProviderCategory).where(
                ProviderCategory.provider_profile_id == provider_profile_id,
            )
        )
        db.add_all(
            ProviderCategory(
                provider_profile_id=provider_profile_id,
                category_slug=category_slug,
            )
            for category_slug in category_slugs
        )
        db.commit()
        return ProviderRepository.get_category_slugs(
            db,
            provider_profile_id=provider_profile_id,
        )

    @staticmethod
    def delete_category_slug(db: Session, *, category_slug: str) -> None:
        db.execute(
            delete(ProviderCategory).where(
                ProviderCategory.category_slug == category_slug,
            )
        )

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: int,
        shop_company_name: str,
        owner_name: str,
        whatsapp_mobile_number: str,
        email: str,
        aadhaar_front_path: str,
        aadhaar_back_path: str,
        payment_bill_path: str,
        electricity_bill_path: str,
        latitude: float | None,
        longitude: float | None,
    ) -> ProviderProfile:
        profile = ProviderProfile(
            user_id=user_id,
            shop_company_name=shop_company_name,
            owner_name=owner_name,
            whatsapp_mobile_number=whatsapp_mobile_number,
            email=email.lower(),
            aadhaar_front_path=aadhaar_front_path,
            aadhaar_back_path=aadhaar_back_path,
            payment_bill_path=payment_bill_path,
            electricity_bill_path=electricity_bill_path,
            latitude=latitude,
            longitude=longitude,
            verification_status=ProviderVerificationStatus.PENDING.value,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def update_verification_status(
        db: Session,
        *,
        profile: ProviderProfile,
        verification_status: ProviderVerificationStatus,
        rejection_reason: str | None = None,
    ) -> ProviderProfile:
        profile.verification_status = verification_status.value
        profile.rejection_reason = (
            rejection_reason.strip()
            if verification_status == ProviderVerificationStatus.REJECTED and rejection_reason
            else None
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def update_profile(
        db: Session,
        *,
        profile: ProviderProfile,
        user: User,
        shop_company_name: str,
        owner_name: str,
        whatsapp_mobile_number: str,
        email: str,
        latitude: float | None,
        longitude: float | None,
    ) -> ProviderProfile:
        if user.phone != whatsapp_mobile_number:
            db.add(
                UserPhoneHistory(
                    user_id=user.id,
                    old_phone=user.phone,
                    new_phone=whatsapp_mobile_number,
                )
            )

        user.phone = whatsapp_mobile_number
        user.email = email.lower()
        user.full_name = owner_name
        profile.shop_company_name = shop_company_name
        profile.owner_name = owner_name
        profile.whatsapp_mobile_number = whatsapp_mobile_number
        profile.email = email.lower()
        profile.latitude = latitude
        profile.longitude = longitude
        db.add(user)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def apply_document_path(
        db: Session,
        *,
        profile: ProviderProfile,
        document_type: str,
        document_path: str,
    ) -> ProviderProfile:
        document_field_by_type = {
            "aadhaar_front": "aadhaar_front_path",
            "aadhaar_back": "aadhaar_back_path",
            "payment_bill": "payment_bill_path",
            "electricity_bill": "electricity_bill_path",
        }
        field_name = document_field_by_type[document_type]
        setattr(profile, field_name, document_path)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
