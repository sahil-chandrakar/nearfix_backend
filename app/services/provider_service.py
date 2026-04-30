from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.provider_document_change_request import (
    ProviderDocumentChangeRequest,
    ProviderDocumentChangeStatus,
    ProviderDocumentType,
)
from app.models.provider_profile import ProviderProfile
from app.models.user import User
from app.repositories.provider_document_repository import ProviderDocumentRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.provider import ProviderPasswordUpdate, ProviderProfileUpdate


class ProviderService:
    @staticmethod
    def update_profile(
        db: Session,
        *,
        user: User,
        profile: ProviderProfile,
        payload: ProviderProfileUpdate,
    ) -> ProviderProfile:
        phone = payload.whatsapp_mobile_number.strip()
        existing_phone_user = UserRepository.get_by_phone(db, phone=phone)
        if existing_phone_user is not None and existing_phone_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this phone number already exists",
            )

        email = str(payload.email).lower()
        existing_email_user = UserRepository.get_by_email(db, email=email)
        if existing_email_user is not None and existing_email_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        return ProviderRepository.update_profile(
            db,
            profile=profile,
            user=user,
            shop_company_name=payload.shop_company_name,
            owner_name=payload.owner_name,
            whatsapp_mobile_number=phone,
            email=email,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )

    @staticmethod
    def change_password(
        db: Session,
        *,
        user: User,
        payload: ProviderPasswordUpdate,
    ) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )

        user.hashed_password = get_password_hash(payload.new_password)
        db.add(user)
        db.commit()

    @staticmethod
    def create_document_request(
        db: Session,
        *,
        provider_profile_id: int,
        document_type: ProviderDocumentType,
        document_path: str,
    ) -> ProviderDocumentChangeRequest:
        return ProviderDocumentRepository.create(
            db,
            provider_profile_id=provider_profile_id,
            document_type=document_type,
            document_path=document_path,
        )

    @staticmethod
    def list_document_requests(
        db: Session,
        *,
        provider_profile_id: int,
    ) -> list[ProviderDocumentChangeRequest]:
        return ProviderDocumentRepository.list_for_provider(
            db,
            provider_profile_id=provider_profile_id,
        )

    @staticmethod
    def list_pending_document_requests(
        db: Session,
    ) -> list[ProviderDocumentChangeRequest]:
        return ProviderDocumentRepository.list_pending(db)

    @staticmethod
    def review_document_request(
        db: Session,
        *,
        request_id: int,
        review_status: ProviderDocumentChangeStatus,
        admin_user: User | None = None,
        reason: str | None = None,
    ) -> ProviderDocumentChangeRequest:
        if review_status == ProviderDocumentChangeStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Document request can only be approved or rejected",
            )

        request = ProviderDocumentRepository.get_by_id(db, request_id)
        if request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document change request not found",
            )

        if request.status != ProviderDocumentChangeStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document change request has already been reviewed",
            )

        if review_status == ProviderDocumentChangeStatus.APPROVED:
            ProviderRepository.apply_document_path(
                db,
                profile=request.provider_profile,
                document_type=request.document_type,
                document_path=request.document_path,
            )

        return ProviderDocumentRepository.update_status(
            db,
            request=request,
            status=review_status,
            admin_user_id=admin_user.id if admin_user is not None else None,
            rejection_reason=reason,
        )
