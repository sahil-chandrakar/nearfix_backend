from app.schemas.base import CamelModel


class ServiceCategoryRead(CamelModel):
    id: int | None = None
    slug: str
    label: str
    group: str
    is_active: bool = True
    display_order: int = 0


class ServiceCategoryCreate(CamelModel):
    label: str


class ServiceCategoryUpdate(CamelModel):
    label: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


class ProviderCategoriesUpdate(CamelModel):
    category_slugs: list[str]


class ProviderCategoriesRead(CamelModel):
    category_slugs: list[str]


class CustomerBookingRead(CamelModel):
    id: int | None = None
    status: str = "empty"
    message: str


class CustomerProviderSearchResult(CamelModel):
    provider_id: int
    shop_company_name: str
    owner_name: str
    whatsapp_mobile_number: str
    email: str
    latitude: float | None
    longitude: float | None
    verification_status: str
    category_slugs: list[str]
    distance_km: float | None
