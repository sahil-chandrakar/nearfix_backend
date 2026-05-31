from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models.customer_brand import CustomerBrand
from app.models.customer_brand_service import CustomerBrandService
from app.models.customer_brand_store import CustomerBrandStore


SEEDED_CUSTOMER_BRANDS = (
    ("samsung-service", "Samsung Service (Mobile + AC/Fridge/TV)"),
    ("lg-whirlpool-ifb-service", "LG / Whirlpool / IFB Service (Home Appliances)"),
    ("maruti-suzuki-hyundai-car-service", "Maruti Suzuki & Hyundai Car Service"),
    ("hero-honda-bike-service", "Hero & Honda Bike Service"),
)


class BrandRepository:
    @staticmethod
    def ensure_seeded(db: Session) -> None:
        if db.scalar(select(CustomerBrand.id).limit(1)) is not None:
            return

        db.add_all(
            CustomerBrand(slug=slug, name=name, display_order=index)
            for index, (slug, name) in enumerate(SEEDED_CUSTOMER_BRANDS, start=1)
        )
        db.commit()

    @staticmethod
    def list_brands(db: Session, *, active_only: bool = True) -> list[CustomerBrand]:
        BrandRepository.ensure_seeded(db)
        statement = select(CustomerBrand)
        if active_only:
            statement = statement.where(CustomerBrand.is_active.is_(True))
        return list(
            db.scalars(
                statement.order_by(
                    CustomerBrand.display_order,
                    CustomerBrand.name,
                    CustomerBrand.id,
                )
            )
        )

    @staticmethod
    def get_brand_by_id(db: Session, *, brand_id: int) -> CustomerBrand | None:
        BrandRepository.ensure_seeded(db)
        return db.scalar(select(CustomerBrand).where(CustomerBrand.id == brand_id))

    @staticmethod
    def get_brand_by_slug(
        db: Session,
        *,
        slug: str,
        active_only: bool = True,
    ) -> CustomerBrand | None:
        BrandRepository.ensure_seeded(db)
        statement = select(CustomerBrand).where(CustomerBrand.slug == slug)
        if active_only:
            statement = statement.where(CustomerBrand.is_active.is_(True))
        return db.scalar(statement)

    @staticmethod
    def create_brand(db: Session, *, slug: str, name: str, display_order: int) -> CustomerBrand:
        brand = CustomerBrand(slug=slug, name=name, display_order=display_order)
        db.add(brand)
        db.commit()
        db.refresh(brand)
        return brand

    @staticmethod
    def update_brand(
        db: Session,
        *,
        brand: CustomerBrand,
        name: str | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> CustomerBrand:
        if name is not None:
            brand.name = name
        if display_order is not None:
            brand.display_order = display_order
        if is_active is not None:
            brand.is_active = is_active
        db.add(brand)
        db.commit()
        db.refresh(brand)
        return brand

    @staticmethod
    def next_brand_order(db: Session) -> int:
        brands = BrandRepository.list_brands(db, active_only=False)
        return (max((brand.display_order for brand in brands), default=0)) + 1

    @staticmethod
    def list_brand_services(
        db: Session,
        *,
        brand_id: int,
        active_only: bool = True,
    ) -> list[CustomerBrandService]:
        statement = select(CustomerBrandService).where(CustomerBrandService.brand_id == brand_id)
        if active_only:
            statement = statement.where(CustomerBrandService.is_active.is_(True))
        return list(
            db.scalars(
                statement.order_by(
                    CustomerBrandService.display_order,
                    CustomerBrandService.category_slug,
                    CustomerBrandService.id,
                )
            )
        )

    @staticmethod
    def get_brand_service_by_id(
        db: Session,
        *,
        brand_service_id: int,
    ) -> CustomerBrandService | None:
        return db.scalar(
            select(CustomerBrandService).where(CustomerBrandService.id == brand_service_id)
        )

    @staticmethod
    def get_brand_service_by_slug(
        db: Session,
        *,
        brand_id: int,
        category_slug: str,
        active_only: bool = True,
    ) -> CustomerBrandService | None:
        statement = select(CustomerBrandService).where(
            CustomerBrandService.brand_id == brand_id,
            CustomerBrandService.category_slug == category_slug,
        )
        if active_only:
            statement = statement.where(CustomerBrandService.is_active.is_(True))
        return db.scalar(statement)

    @staticmethod
    def create_brand_service(
        db: Session,
        *,
        brand_id: int,
        category_slug: str,
        display_order: int,
    ) -> CustomerBrandService:
        brand_service = CustomerBrandService(
            brand_id=brand_id,
            category_slug=category_slug,
            display_order=display_order,
        )
        db.add(brand_service)
        db.commit()
        db.refresh(brand_service)
        return brand_service

    @staticmethod
    def update_brand_service(
        db: Session,
        *,
        brand_service: CustomerBrandService,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> CustomerBrandService:
        if display_order is not None:
            brand_service.display_order = display_order
        if is_active is not None:
            brand_service.is_active = is_active
        db.add(brand_service)
        db.commit()
        db.refresh(brand_service)
        return brand_service

    @staticmethod
    def next_brand_service_order(db: Session, *, brand_id: int) -> int:
        services = BrandRepository.list_brand_services(
            db,
            brand_id=brand_id,
            active_only=False,
        )
        return (max((service.display_order for service in services), default=0)) + 1

    @staticmethod
    def delete_brand_services_by_category(db: Session, *, category_slug: str) -> None:
        db.execute(
            delete(CustomerBrandService).where(
                CustomerBrandService.category_slug == category_slug,
            )
        )

    @staticmethod
    def list_brand_stores(
        db: Session,
        *,
        brand_service_id: int,
        active_only: bool = True,
    ) -> list[CustomerBrandStore]:
        statement = (
            select(CustomerBrandStore)
            .options(joinedload(CustomerBrandStore.provider_profile))
            .where(CustomerBrandStore.brand_service_id == brand_service_id)
        )
        if active_only:
            statement = statement.where(CustomerBrandStore.is_active.is_(True))
        return list(
            db.scalars(
                statement.order_by(
                    CustomerBrandStore.display_order,
                    CustomerBrandStore.id,
                )
            )
        )

    @staticmethod
    def get_brand_store_by_id(db: Session, *, store_id: int) -> CustomerBrandStore | None:
        return db.scalar(
            select(CustomerBrandStore)
            .options(joinedload(CustomerBrandStore.provider_profile))
            .where(CustomerBrandStore.id == store_id)
        )

    @staticmethod
    def get_provider_brand_store(
        db: Session,
        *,
        brand_service_id: int,
        provider_profile_id: int,
    ) -> CustomerBrandStore | None:
        return db.scalar(
            select(CustomerBrandStore).where(
                CustomerBrandStore.brand_service_id == brand_service_id,
                CustomerBrandStore.provider_profile_id == provider_profile_id,
            )
        )

    @staticmethod
    def create_provider_store(
        db: Session,
        *,
        brand_service_id: int,
        provider_profile_id: int,
        display_order: int,
    ) -> CustomerBrandStore:
        store = CustomerBrandStore(
            brand_service_id=brand_service_id,
            provider_profile_id=provider_profile_id,
            display_order=display_order,
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        return store

    @staticmethod
    def create_manual_store(
        db: Session,
        *,
        brand_service_id: int,
        shop_name: str,
        contact_name: str,
        phone: str,
        email: str | None,
        latitude: float | None,
        longitude: float | None,
        display_order: int,
    ) -> CustomerBrandStore:
        store = CustomerBrandStore(
            brand_service_id=brand_service_id,
            shop_name=shop_name,
            contact_name=contact_name,
            phone=phone,
            email=email,
            latitude=latitude,
            longitude=longitude,
            display_order=display_order,
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        return store

    @staticmethod
    def update_brand_store(
        db: Session,
        *,
        store: CustomerBrandStore,
        shop_name: str | None = None,
        contact_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
        update_email: bool = False,
        update_latitude: bool = False,
        update_longitude: bool = False,
    ) -> CustomerBrandStore:
        if shop_name is not None:
            store.shop_name = shop_name
        if contact_name is not None:
            store.contact_name = contact_name
        if phone is not None:
            store.phone = phone
        if update_email:
            store.email = email
        if update_latitude:
            store.latitude = latitude
        if update_longitude:
            store.longitude = longitude
        if display_order is not None:
            store.display_order = display_order
        if is_active is not None:
            store.is_active = is_active
        db.add(store)
        db.commit()
        db.refresh(store)
        return store

    @staticmethod
    def next_store_order(db: Session, *, brand_service_id: int) -> int:
        stores = BrandRepository.list_brand_stores(
            db,
            brand_service_id=brand_service_id,
            active_only=False,
        )
        return (max((store.display_order for store in stores), default=0)) + 1
