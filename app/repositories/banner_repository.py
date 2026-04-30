from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.customer_home_banner import CustomerHomeBanner


class BannerRepository:
    banner_limit_key = "customer_home_banner_limit"

    @staticmethod
    def get_banner_limit(db: Session) -> int:
        setting = db.get(AppSetting, BannerRepository.banner_limit_key)
        if setting is None:
            setting = AppSetting(key=BannerRepository.banner_limit_key, value="2")
            db.add(setting)
            db.commit()
            return 2
        try:
            return max(1, min(10, int(setting.value)))
        except ValueError:
            return 2

    @staticmethod
    def set_banner_limit(db: Session, *, banner_limit: int) -> int:
        setting = db.get(AppSetting, BannerRepository.banner_limit_key)
        if setting is None:
            setting = AppSetting(key=BannerRepository.banner_limit_key, value=str(banner_limit))
        else:
            setting.value = str(banner_limit)
        db.add(setting)
        db.commit()
        return banner_limit

    @staticmethod
    def list_banners(db: Session, *, active_only: bool = False) -> list[CustomerHomeBanner]:
        statement = select(CustomerHomeBanner)
        if active_only:
            statement = statement.where(CustomerHomeBanner.is_active.is_(True))
        return list(
            db.scalars(
                statement.order_by(
                    CustomerHomeBanner.display_order,
                    CustomerHomeBanner.id,
                )
            )
        )

    @staticmethod
    def list_active_for_customer(db: Session) -> list[CustomerHomeBanner]:
        limit = BannerRepository.get_banner_limit(db)
        return BannerRepository.list_banners(db, active_only=True)[:limit]

    @staticmethod
    def get_by_id(db: Session, *, banner_id: int) -> CustomerHomeBanner | None:
        return db.scalar(select(CustomerHomeBanner).where(CustomerHomeBanner.id == banner_id))

    @staticmethod
    def create(
        db: Session,
        *,
        image_path: str,
        alt_text: str,
        display_order: int,
    ) -> CustomerHomeBanner:
        banner = CustomerHomeBanner(
            image_path=image_path,
            alt_text=alt_text,
            display_order=display_order,
        )
        db.add(banner)
        db.commit()
        db.refresh(banner)
        return banner

    @staticmethod
    def update(
        db: Session,
        *,
        banner: CustomerHomeBanner,
        alt_text: str | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> CustomerHomeBanner:
        if alt_text is not None:
            banner.alt_text = alt_text
        if display_order is not None:
            banner.display_order = display_order
        if is_active is not None:
            banner.is_active = is_active
        db.add(banner)
        db.commit()
        db.refresh(banner)
        return banner

    @staticmethod
    def delete(db: Session, *, banner: CustomerHomeBanner) -> None:
        db.delete(banner)
        db.commit()

    @staticmethod
    def next_display_order(db: Session) -> int:
        banners = BannerRepository.list_banners(db)
        return (max((banner.display_order for banner in banners), default=0)) + 1
