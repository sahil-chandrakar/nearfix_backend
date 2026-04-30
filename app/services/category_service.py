from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.provider_profile import ProviderProfile
from app.repositories.provider_repository import ProviderRepository
from app.repositories.service_category_repository import ServiceCategoryRepository
from app.schemas.category import CustomerProviderSearchResult, ServiceCategoryRead


class CategoryService:
    @staticmethod
    def list_categories(db: Session, *, active_only: bool = True) -> list[ServiceCategoryRead]:
        return [
            ServiceCategoryRead(
                id=category.id,
                slug=category.slug,
                label=category.label,
                group=category.group,
                is_active=category.is_active,
                display_order=category.display_order,
            )
            for category in ServiceCategoryRepository.list_categories(
                db,
                active_only=active_only,
            )
        ]

    @staticmethod
    def validate_category_slugs(db: Session, category_slugs: list[str]) -> list[str]:
        cleaned_slugs = list(dict.fromkeys(category_slugs))
        invalid_slugs = [
            category_slug
            for category_slug in cleaned_slugs
            if ServiceCategoryRepository.get_by_slug(db, slug=category_slug) is None
        ]
        if invalid_slugs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid category slug: {invalid_slugs[0]}",
            )
        return cleaned_slugs

    @staticmethod
    def get_provider_category_slugs(db: Session, provider_profile_id: int) -> list[str]:
        return ProviderRepository.get_category_slugs(
            db,
            provider_profile_id=provider_profile_id,
        )

    @staticmethod
    def set_provider_category_slugs(
        db: Session,
        *,
        provider_profile_id: int,
        category_slugs: list[str],
    ) -> list[str]:
        cleaned_slugs = CategoryService.validate_category_slugs(db, category_slugs)
        return ProviderRepository.set_category_slugs(
            db,
            provider_profile_id=provider_profile_id,
            category_slugs=cleaned_slugs,
        )

    @staticmethod
    def search_customer_providers(
        db: Session,
        *,
        category_slug: str,
        latitude: float | None,
        longitude: float | None,
    ) -> list[CustomerProviderSearchResult]:
        CategoryService.validate_category_slugs(db, [category_slug])
        providers = ProviderRepository.list_approved_by_category(
            db,
            category_slug=category_slug,
        )
        results = [
            CategoryService._provider_to_search_result(
                db,
                provider=provider,
                latitude=latitude,
                longitude=longitude,
            )
            for provider in providers
        ]
        return sorted(
            results,
            key=lambda result: (
                result.distance_km is None,
                result.distance_km if result.distance_km is not None else 0,
                result.shop_company_name.lower(),
            ),
        )

    @staticmethod
    def _provider_to_search_result(
        db: Session,
        *,
        provider: ProviderProfile,
        latitude: float | None,
        longitude: float | None,
    ) -> CustomerProviderSearchResult:
        distance_km = None
        if (
            latitude is not None
            and longitude is not None
            and provider.latitude is not None
            and provider.longitude is not None
        ):
            distance_km = round(
                CategoryService._distance_km(
                    latitude,
                    longitude,
                    provider.latitude,
                    provider.longitude,
                ),
                1,
            )

        return CustomerProviderSearchResult(
            provider_id=provider.id,
            shop_company_name=provider.shop_company_name,
            owner_name=provider.owner_name,
            whatsapp_mobile_number=provider.whatsapp_mobile_number,
            email=provider.email,
            latitude=provider.latitude,
            longitude=provider.longitude,
            verification_status=provider.verification_status,
            category_slugs=ProviderRepository.get_category_slugs(
                db,
                provider_profile_id=provider.id,
            ),
            distance_km=distance_km,
        )

    @staticmethod
    def get_category_label(db: Session, *, category_slug: str) -> str:
        category = ServiceCategoryRepository.get_by_slug(
            db,
            slug=category_slug,
            active_only=False,
        )
        return category.label if category is not None else category_slug

    @staticmethod
    def _distance_km(
        latitude_a: float,
        longitude_a: float,
        latitude_b: float,
        longitude_b: float,
    ) -> float:
        earth_radius_km = 6371.0
        delta_latitude = radians(latitude_b - latitude_a)
        delta_longitude = radians(longitude_b - longitude_a)
        point_a_latitude = radians(latitude_a)
        point_b_latitude = radians(latitude_b)

        haversine = (
            sin(delta_latitude / 2) ** 2
            + cos(point_a_latitude)
            * cos(point_b_latitude)
            * sin(delta_longitude / 2) ** 2
        )
        return 2 * earth_radius_km * asin(sqrt(haversine))
