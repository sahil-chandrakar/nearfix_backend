from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.categories import SERVICE_CATEGORIES
from app.models.service_category import ServiceCategory


class ServiceCategoryRepository:
    @staticmethod
    def ensure_seeded(db: Session) -> None:
        if db.scalar(select(ServiceCategory.id).limit(1)) is not None:
            return

        db.add_all(
            ServiceCategory(
                slug=category.slug,
                label=category.label,
                group=category.group,
                display_order=index,
            )
            for index, category in enumerate(SERVICE_CATEGORIES, start=1)
        )
        db.commit()

    @staticmethod
    def list_categories(db: Session, *, active_only: bool = True) -> list[ServiceCategory]:
        ServiceCategoryRepository.ensure_seeded(db)
        statement = select(ServiceCategory)
        if active_only:
            statement = statement.where(ServiceCategory.is_active.is_(True))
        return list(
            db.scalars(
                statement.order_by(
                    ServiceCategory.display_order,
                    ServiceCategory.label,
                    ServiceCategory.id,
                )
            )
        )

    @staticmethod
    def get_by_slug(db: Session, *, slug: str, active_only: bool = True) -> ServiceCategory | None:
        ServiceCategoryRepository.ensure_seeded(db)
        statement = select(ServiceCategory).where(ServiceCategory.slug == slug)
        if active_only:
            statement = statement.where(ServiceCategory.is_active.is_(True))
        return db.scalar(statement)

    @staticmethod
    def get_by_id(db: Session, *, category_id: int) -> ServiceCategory | None:
        ServiceCategoryRepository.ensure_seeded(db)
        return db.scalar(select(ServiceCategory).where(ServiceCategory.id == category_id))

    @staticmethod
    def create(
        db: Session,
        *,
        slug: str,
        label: str,
        group: str,
        display_order: int,
    ) -> ServiceCategory:
        category = ServiceCategory(
            slug=slug,
            label=label,
            group=group,
            display_order=display_order,
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def update(
        db: Session,
        *,
        category: ServiceCategory,
        label: str | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> ServiceCategory:
        if label is not None:
            category.label = label
        if display_order is not None:
            category.display_order = display_order
        if is_active is not None:
            category.is_active = is_active
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    @staticmethod
    def next_display_order(db: Session, *, group: str) -> int:
        ServiceCategoryRepository.ensure_seeded(db)
        categories = ServiceCategoryRepository.list_categories(db, active_only=False)
        group_orders = [category.display_order for category in categories if category.group == group]
        return (max(group_orders) if group_orders else len(categories)) + 1
