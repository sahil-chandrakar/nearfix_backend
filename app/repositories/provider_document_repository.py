from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.provider_document_change_request import (
    ProviderDocumentChangeRequest,
    ProviderDocumentChangeStatus,
    ProviderDocumentType,
)


class ProviderDocumentRepository:
    @staticmethod
    def get_by_id(db: Session, request_id: int) -> ProviderDocumentChangeRequest | None:
        return db.scalar(
            select(ProviderDocumentChangeRequest)
            .options(joinedload(ProviderDocumentChangeRequest.provider_profile))
            .where(ProviderDocumentChangeRequest.id == request_id)
        )

    @staticmethod
    def create(
        db: Session,
        *,
        provider_profile_id: int,
        document_type: ProviderDocumentType,
        document_path: str,
    ) -> ProviderDocumentChangeRequest:
        request = ProviderDocumentChangeRequest(
            provider_profile_id=provider_profile_id,
            document_type=document_type.value,
            document_path=document_path,
            status=ProviderDocumentChangeStatus.PENDING.value,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def list_for_provider(
        db: Session,
        *,
        provider_profile_id: int,
    ) -> list[ProviderDocumentChangeRequest]:
        return list(
            db.scalars(
                select(ProviderDocumentChangeRequest)
                .where(ProviderDocumentChangeRequest.provider_profile_id == provider_profile_id)
                .order_by(
                    ProviderDocumentChangeRequest.created_at.desc(),
                    ProviderDocumentChangeRequest.id.desc(),
                )
            )
        )

    @staticmethod
    def list_by_status(
        db: Session,
        *,
        status: ProviderDocumentChangeStatus | None = None,
    ) -> list[ProviderDocumentChangeRequest]:
        statement = select(ProviderDocumentChangeRequest).options(
            joinedload(ProviderDocumentChangeRequest.provider_profile)
        )
        if status is not None:
            statement = statement.where(ProviderDocumentChangeRequest.status == status.value)
        return list(
            db.scalars(
                statement.order_by(
                    ProviderDocumentChangeRequest.created_at.desc(),
                    ProviderDocumentChangeRequest.id.desc(),
                )
            )
        )

    @staticmethod
    def list_pending(db: Session) -> list[ProviderDocumentChangeRequest]:
        return list(
            db.scalars(
                select(ProviderDocumentChangeRequest)
                .options(joinedload(ProviderDocumentChangeRequest.provider_profile))
                .where(
                    ProviderDocumentChangeRequest.status
                    == ProviderDocumentChangeStatus.PENDING.value,
                )
                .order_by(
                    ProviderDocumentChangeRequest.created_at.desc(),
                    ProviderDocumentChangeRequest.id.desc(),
                )
            )
        )

    @staticmethod
    def update_status(
        db: Session,
        *,
        request: ProviderDocumentChangeRequest,
        status: ProviderDocumentChangeStatus,
        admin_user_id: int | None = None,
        rejection_reason: str | None = None,
    ) -> ProviderDocumentChangeRequest:
        request.status = status.value
        request.reviewed_by_admin_id = admin_user_id
        request.rejection_reason = (
            rejection_reason.strip()
            if status == ProviderDocumentChangeStatus.REJECTED and rejection_reason
            else None
        )
        request.reviewed_at = datetime.now(timezone.utc)
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
