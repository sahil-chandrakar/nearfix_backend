from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CustomerBrandService(Base):
    __tablename__ = "customer_brand_services"
    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "category_slug",
            name="uq_customer_brand_services_brand_slug",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("customer_brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    category_slug: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
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

    brand: Mapped["CustomerBrand"] = relationship(back_populates="services")
    stores: Mapped[list["CustomerBrandStore"]] = relationship(
        back_populates="brand_service",
        cascade="all, delete-orphan",
    )
