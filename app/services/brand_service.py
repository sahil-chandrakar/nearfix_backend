import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.customer_brand import CustomerBrand
from app.models.customer_brand_service import CustomerBrandService as CustomerBrandServiceModel
from app.models.customer_brand_store import CustomerBrandStore
from app.models.provider_profile import ProviderProfile, ProviderVerificationStatus
from app.repositories.brand_repository import BrandRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.service_category_repository import ServiceCategoryRepository
from app.schemas.brand import (
    BrandManualStoreCreate,
    BrandProviderStoreCreate,
    BrandRead,
    BrandServiceCreate,
    BrandServiceRead,
    BrandServiceUpdate,
    BrandStoreRead,
    BrandStoreUpdate,
)


class BrandService:
    @staticmethod
    def list_brands(db: Session, *, active_only: bool = True) -> list[BrandRead]:
        return [
            BrandService._brand_to_read(brand)
            for brand in BrandRepository.list_brands(db, active_only=active_only)
        ]

    @staticmethod
    def create_brand(db: Session, *, name: str) -> BrandRead:
        clean_name = name.strip()
        if len(clean_name) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Brand name is too short",
            )
        brand = BrandRepository.create_brand(
            db,
            slug=BrandService._unique_brand_slug(db, clean_name),
            name=clean_name,
            display_order=BrandRepository.next_brand_order(db),
        )
        return BrandService._brand_to_read(brand)

    @staticmethod
    def update_brand(
        db: Session,
        *,
        brand_id: int,
        name: str | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> BrandRead:
        brand = BrandRepository.get_brand_by_id(db, brand_id=brand_id)
        if brand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
        clean_name = name.strip() if name is not None else None
        if clean_name is not None and len(clean_name) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Brand name is too short",
            )
        updated = BrandRepository.update_brand(
            db,
            brand=brand,
            name=clean_name,
            display_order=display_order,
            is_active=is_active,
        )
        return BrandService._brand_to_read(updated)

    @staticmethod
    def list_admin_brand_services(db: Session, *, brand_id: int) -> list[BrandServiceRead]:
        brand = BrandRepository.get_brand_by_id(db, brand_id=brand_id)
        if brand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
        return BrandService._brand_services_to_read(
            db,
            BrandRepository.list_brand_services(db, brand_id=brand_id, active_only=False),
            active_category_only=False,
        )

    @staticmethod
    def list_customer_brand_services(db: Session, *, brand_slug: str) -> list[BrandServiceRead]:
        brand = BrandRepository.get_brand_by_slug(db, slug=brand_slug)
        if brand is None:
            return []
        return BrandService._brand_services_to_read(
            db,
            BrandRepository.list_brand_services(db, brand_id=brand.id),
            active_category_only=True,
        )

    @staticmethod
    def create_brand_service(
        db: Session,
        *,
        brand_id: int,
        payload: BrandServiceCreate,
    ) -> BrandServiceRead:
        brand = BrandRepository.get_brand_by_id(db, brand_id=brand_id)
        if brand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
        category = ServiceCategoryRepository.get_by_slug(db, slug=payload.category_slug)
        if category is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Service not found")
        existing = BrandRepository.get_brand_service_by_slug(
            db,
            brand_id=brand_id,
            category_slug=payload.category_slug,
            active_only=False,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service already added to this brand",
            )
        brand_service = BrandRepository.create_brand_service(
            db,
            brand_id=brand_id,
            category_slug=payload.category_slug,
            display_order=BrandRepository.next_brand_service_order(db, brand_id=brand_id),
        )
        return BrandService._brand_service_to_read(
            db,
            brand_service,
            active_category_only=False,
        )

    @staticmethod
    def update_brand_service(
        db: Session,
        *,
        brand_service_id: int,
        payload: BrandServiceUpdate,
    ) -> BrandServiceRead:
        brand_service = BrandRepository.get_brand_service_by_id(
            db,
            brand_service_id=brand_service_id,
        )
        if brand_service is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand service not found")
        updated = BrandRepository.update_brand_service(
            db,
            brand_service=brand_service,
            display_order=payload.display_order,
            is_active=payload.is_active,
        )
        return BrandService._brand_service_to_read(
            db,
            updated,
            active_category_only=False,
        )

    @staticmethod
    def list_admin_brand_stores(db: Session, *, brand_service_id: int) -> list[BrandStoreRead]:
        brand_service = BrandRepository.get_brand_service_by_id(
            db,
            brand_service_id=brand_service_id,
        )
        if brand_service is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand service not found")
        return [
            read
            for store in BrandRepository.list_brand_stores(
                db,
                brand_service_id=brand_service_id,
                active_only=False,
            )
            if (
                read := BrandService._store_to_read(
                    store,
                    latitude=None,
                    longitude=None,
                    customer_visible=False,
                )
            )
            is not None
        ]

    @staticmethod
    def list_customer_brand_stores(
        db: Session,
        *,
        brand_slug: str,
        category_slug: str,
        latitude: float | None,
        longitude: float | None,
    ) -> list[BrandStoreRead]:
        brand = BrandRepository.get_brand_by_slug(db, slug=brand_slug)
        if brand is None:
            return []
        brand_service = BrandRepository.get_brand_service_by_slug(
            db,
            brand_id=brand.id,
            category_slug=category_slug,
        )
        if brand_service is None:
            return []
        if ServiceCategoryRepository.get_by_slug(db, slug=category_slug) is None:
            return []
        return [
            read
            for store in BrandRepository.list_brand_stores(
                db,
                brand_service_id=brand_service.id,
            )
            if (
                read := BrandService._store_to_read(
                    store,
                    latitude=latitude,
                    longitude=longitude,
                    customer_visible=True,
                )
            )
            is not None
        ]

    @staticmethod
    def create_provider_store(
        db: Session,
        *,
        brand_service_id: int,
        payload: BrandProviderStoreCreate,
    ) -> BrandStoreRead:
        brand_service = BrandRepository.get_brand_service_by_id(
            db,
            brand_service_id=brand_service_id,
        )
        if brand_service is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand service not found")
        provider = ProviderRepository.get_by_id(db, payload.provider_profile_id)
        if provider is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        if provider.verification_status != ProviderVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only approved providers can be added",
            )
        provider_category_slugs = ProviderRepository.get_category_slugs(
            db,
            provider_profile_id=provider.id,
        )
        if brand_service.category_slug not in provider_category_slugs:
            ProviderRepository.set_category_slugs(
                db,
                provider_profile_id=provider.id,
                category_slugs=[*provider_category_slugs, brand_service.category_slug],
            )
        existing = BrandRepository.get_provider_brand_store(
            db,
            brand_service_id=brand_service_id,
            provider_profile_id=payload.provider_profile_id,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider store already added",
            )
        store = BrandRepository.create_provider_store(
            db,
            brand_service_id=brand_service_id,
            provider_profile_id=payload.provider_profile_id,
            display_order=payload.display_order
            if payload.display_order is not None
            else BrandRepository.next_store_order(db, brand_service_id=brand_service_id),
        )
        store.provider_profile = provider
        read = BrandService._store_to_read(
            store,
            latitude=None,
            longitude=None,
            customer_visible=False,
        )
        assert read is not None
        return read

    @staticmethod
    def create_manual_store(
        db: Session,
        *,
        brand_service_id: int,
        payload: BrandManualStoreCreate,
    ) -> BrandStoreRead:
        brand_service = BrandRepository.get_brand_service_by_id(
            db,
            brand_service_id=brand_service_id,
        )
        if brand_service is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand service not found")
        store = BrandRepository.create_manual_store(
            db,
            brand_service_id=brand_service_id,
            shop_name=payload.shop_name.strip(),
            contact_name=payload.contact_name.strip(),
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            latitude=payload.latitude,
            longitude=payload.longitude,
            display_order=payload.display_order
            if payload.display_order is not None
            else BrandRepository.next_store_order(db, brand_service_id=brand_service_id),
        )
        read = BrandService._store_to_read(
            store,
            latitude=None,
            longitude=None,
            customer_visible=False,
        )
        assert read is not None
        return read

    @staticmethod
    def update_brand_store(
        db: Session,
        *,
        store_id: int,
        payload: BrandStoreUpdate,
    ) -> BrandStoreRead:
        store = BrandRepository.get_brand_store_by_id(db, store_id=store_id)
        if store is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand store not found")
        payload_data = payload.model_dump(exclude_unset=True)
        updated = BrandRepository.update_brand_store(
            db,
            store=store,
            shop_name=payload_data.get("shop_name", None).strip()
            if isinstance(payload_data.get("shop_name"), str)
            else None,
            contact_name=payload_data.get("contact_name", None).strip()
            if isinstance(payload_data.get("contact_name"), str)
            else None,
            phone=payload_data.get("phone"),
            email=str(payload_data["email"]) if payload_data.get("email") else None,
            latitude=payload_data.get("latitude"),
            longitude=payload_data.get("longitude"),
            display_order=payload_data.get("display_order"),
            is_active=payload_data.get("is_active"),
            update_email="email" in payload_data,
            update_latitude="latitude" in payload_data,
            update_longitude="longitude" in payload_data,
        )
        read = BrandService._store_to_read(
            updated,
            latitude=None,
            longitude=None,
            customer_visible=False,
        )
        assert read is not None
        return read

    @staticmethod
    def _brand_to_read(brand: CustomerBrand) -> BrandRead:
        return BrandRead(
            id=brand.id,
            slug=brand.slug,
            name=brand.name,
            is_active=brand.is_active,
            display_order=brand.display_order,
            created_at=brand.created_at,
            updated_at=brand.updated_at,
        )

    @staticmethod
    def _brand_services_to_read(
        db: Session,
        brand_services: list[CustomerBrandServiceModel],
        *,
        active_category_only: bool,
    ) -> list[BrandServiceRead]:
        reads: list[BrandServiceRead] = []
        for brand_service in brand_services:
            read = BrandService._brand_service_to_read(
                db,
                brand_service,
                active_category_only=active_category_only,
            )
            if read is not None:
                reads.append(read)
        return reads

    @staticmethod
    def _brand_service_to_read(
        db: Session,
        brand_service: CustomerBrandServiceModel,
        *,
        active_category_only: bool,
    ) -> BrandServiceRead | None:
        category = ServiceCategoryRepository.get_by_slug(
            db,
            slug=brand_service.category_slug,
            active_only=active_category_only,
        )
        if category is None:
            return None
        return BrandServiceRead(
            id=brand_service.id,
            brand_id=brand_service.brand_id,
            category_slug=brand_service.category_slug,
            label=category.label,
            label_hi=category.label_hi,
            group=category.group,
            group_hi=category.group_hi,
            is_active=brand_service.is_active,
            display_order=brand_service.display_order,
            created_at=brand_service.created_at,
            updated_at=brand_service.updated_at,
        )

    @staticmethod
    def _store_to_read(
        store: CustomerBrandStore,
        *,
        latitude: float | None,
        longitude: float | None,
        customer_visible: bool,
    ) -> BrandStoreRead | None:
        provider = store.provider_profile
        if provider is not None:
            if (
                customer_visible
                and provider.verification_status != ProviderVerificationStatus.APPROVED.value
            ):
                return None
            return BrandService._provider_store_to_read(
                store,
                provider=provider,
                latitude=latitude,
                longitude=longitude,
            )

        if not store.shop_name or not store.contact_name or not store.phone:
            return None
        return BrandService._manual_store_to_read(
            store,
            latitude=latitude,
            longitude=longitude,
        )

    @staticmethod
    def _provider_store_to_read(
        store: CustomerBrandStore,
        *,
        provider: ProviderProfile,
        latitude: float | None,
        longitude: float | None,
    ) -> BrandStoreRead:
        return BrandStoreRead(
            id=store.id,
            brand_service_id=store.brand_service_id,
            store_type="provider",
            provider_profile_id=provider.id,
            shop_name=provider.shop_company_name,
            contact_name=provider.owner_name,
            phone=provider.whatsapp_mobile_number,
            email=provider.email,
            latitude=provider.latitude,
            longitude=provider.longitude,
            is_active=store.is_active,
            display_order=store.display_order,
            distance_km=BrandService._distance_between(
                latitude,
                longitude,
                provider.latitude,
                provider.longitude,
            ),
            created_at=store.created_at,
            updated_at=store.updated_at,
        )

    @staticmethod
    def _manual_store_to_read(
        store: CustomerBrandStore,
        *,
        latitude: float | None,
        longitude: float | None,
    ) -> BrandStoreRead:
        return BrandStoreRead(
            id=store.id,
            brand_service_id=store.brand_service_id,
            store_type="manual",
            provider_profile_id=None,
            shop_name=store.shop_name or "",
            contact_name=store.contact_name or "",
            phone=store.phone or "",
            email=store.email,
            latitude=store.latitude,
            longitude=store.longitude,
            is_active=store.is_active,
            display_order=store.display_order,
            distance_km=BrandService._distance_between(
                latitude,
                longitude,
                store.latitude,
                store.longitude,
            ),
            created_at=store.created_at,
            updated_at=store.updated_at,
        )

    @staticmethod
    def _unique_brand_slug(db: Session, name: str) -> str:
        base_slug = BrandService._slugify(name)
        slug = base_slug
        suffix = 2
        while BrandRepository.get_brand_by_slug(db, slug=slug, active_only=False) is not None:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "brand"

    @staticmethod
    def _distance_between(
        latitude_a: float | None,
        longitude_a: float | None,
        latitude_b: float | None,
        longitude_b: float | None,
    ) -> float | None:
        if (
            latitude_a is None
            or longitude_a is None
            or latitude_b is None
            or longitude_b is None
        ):
            return None
        from app.services.category_service import CategoryService

        return round(
            CategoryService._distance_km(latitude_a, longitude_a, latitude_b, longitude_b),
            1,
        )
