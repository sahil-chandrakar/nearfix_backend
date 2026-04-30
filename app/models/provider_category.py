from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderCategory(Base):
    __tablename__ = "provider_categories"
    __table_args__ = (
        UniqueConstraint(
            "provider_profile_id",
            "category_slug",
            name="uq_provider_categories_profile_slug",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    category_slug: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
