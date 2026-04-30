from datetime import datetime

from pydantic import Field, model_validator

from app.models.provider_document_change_request import (
    ProviderDocumentChangeStatus,
    ProviderDocumentType,
)
from app.schemas.base import CamelModel


class ProviderDocumentChangeRead(CamelModel):
    id: int
    provider_profile_id: int
    document_type: ProviderDocumentType
    document_path: str
    status: ProviderDocumentChangeStatus
    rejection_reason: str | None = None
    reviewed_by_admin_id: int | None = None
    created_at: datetime
    reviewed_at: datetime | None


class ProviderDocumentChangeReview(CamelModel):
    status: ProviderDocumentChangeStatus
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "ProviderDocumentChangeReview":
        if (
            self.status == ProviderDocumentChangeStatus.REJECTED
            and not (self.reason or "").strip()
        ):
            raise ValueError("Rejection reason is required")
        return self
