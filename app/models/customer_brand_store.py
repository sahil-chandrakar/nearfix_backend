from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CustomerBrandStore(Base):
    __tablename__ = "customer_brand_stores"
    __table_args__ = (
        UniqueConstraint(
            "brand_service_id",
            "provider_profile_id",
            name="uq_customer_brand_stores_service_provider",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    brand_service_id: Mapped[int] = mapped_column(
        ForeignKey("customer_brand_services.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    shop_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    brand_service: Mapped["CustomerBrandService"] = relationship(back_populates="stores")
    provider_profile: Mapped["ProviderProfile | None"] = relationship()
