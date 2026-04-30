from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.provider_profile import ProviderProfile


class ProviderDocumentType(StrEnum):
    AADHAAR_FRONT = "aadhaar_front"
    AADHAAR_BACK = "aadhaar_back"
    PAYMENT_BILL = "payment_bill"
    ELECTRICITY_BILL = "electricity_bill"


class ProviderDocumentChangeStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProviderDocumentChangeRequest(Base):
    __tablename__ = "provider_document_change_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_profile_id: Mapped[int] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    document_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ProviderDocumentChangeStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    provider_profile: Mapped["ProviderProfile"] = relationship()
