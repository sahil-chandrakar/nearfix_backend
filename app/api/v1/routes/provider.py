from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jwt import InvalidTokenError
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.api.deps import DBSession, ProviderUser
from app.core.security import create_access_token, decode_access_token
from app.db.session import get_db
from app.models.booking import BookingStatus
from app.models.provider_document_change_request import ProviderDocumentType
from app.models.provider_profile import ProviderProfile, ProviderVerificationStatus
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token
from app.schemas.booking import BookingRead, BookingStatusUpdate
from app.schemas.category import ProviderCategoriesRead, ProviderCategoriesUpdate
from app.schemas.customer import PhoneLoginRequest
from app.schemas.provider import (
    ProviderPasswordUpdate,
    ProviderProfileRead,
    ProviderProfileUpdate,
    ProviderRegistrationData,
)
from app.schemas.provider_document import ProviderDocumentChangeRead
from app.services.auth_service import AuthService
from app.services.booking_notifier import provider_booking_notifier
from app.services.booking_service import BookingService
from app.services.category_service import CategoryService
from app.services.provider_service import ProviderService
from app.services.upload_service import UploadService

router = APIRouter(prefix="/provider", tags=["provider"])


def _provider_profile_for_user(db: DBSession, current_user: ProviderUser) -> ProviderProfile:
    return AuthService.get_provider_profile(db=db, user_id=current_user.id)


def _ensure_not_rejected(profile: ProviderProfile) -> None:
    if profile.verification_status == ProviderVerificationStatus.REJECTED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider verification was rejected",
        )


def _ensure_approved(profile: ProviderProfile) -> None:
    if profile.verification_status != ProviderVerificationStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider must be approved before using this feature",
        )


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
def register_provider(
    shop_company_name: Annotated[
        str,
        Form(alias="shopCompanyName", min_length=2, max_length=255),
    ],
    owner_name: Annotated[
        str,
        Form(alias="ownerName", min_length=2, max_length=255),
    ],
    whatsapp_mobile_number: Annotated[
        str,
        Form(alias="whatsappMobileNumber", pattern=r"^\d{10}$"),
    ],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form(min_length=8, max_length=128)],
    aadhaar_front: Annotated[UploadFile, File(alias="aadhaarFront")],
    aadhaar_back: Annotated[UploadFile, File(alias="aadhaarBack")],
    payment_bill: Annotated[UploadFile, File(alias="paymentBill")],
    electricity_bill: Annotated[UploadFile, File(alias="electricityBill")],
    db: DBSession,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
) -> Token:
    payload = ProviderRegistrationData(
        shop_company_name=shop_company_name,
        owner_name=owner_name,
        whatsapp_mobile_number=whatsapp_mobile_number,
        email=email,
        password=password,
        latitude=latitude,
        longitude=longitude,
    )
    AuthService.ensure_provider_registration_available(db=db, payload=payload)
    phone = AuthService.normalize_phone(whatsapp_mobile_number)
    aadhaar_front_path = UploadService.save_provider_document(
        file=aadhaar_front,
        phone=phone,
        document_name="aadhaar-front",
    )
    aadhaar_back_path = UploadService.save_provider_document(
        file=aadhaar_back,
        phone=phone,
        document_name="aadhaar-back",
    )
    payment_bill_path = UploadService.save_provider_document(
        file=payment_bill,
        phone=phone,
        document_name="payment-bill",
    )
    electricity_bill_path = UploadService.save_provider_document(
        file=electricity_bill,
        phone=phone,
        document_name="electricity-bill",
    )

    user = AuthService.register_provider(
        db=db,
        payload=payload,
        aadhaar_front_path=aadhaar_front_path,
        aadhaar_back_path=aadhaar_back_path,
        payment_bill_path=payment_bill_path,
        electricity_bill_path=electricity_bill_path,
    )
    return Token(access_token=create_access_token(subject=user.id))


@router.post("/login", response_model=Token)
def login_provider(payload: PhoneLoginRequest, db: DBSession) -> Token:
    user = AuthService.authenticate_phone(
        db=db,
        phone=payload.phone,
        password=payload.password,
        expected_role=UserRole.PROVIDER,
    )
    return Token(access_token=create_access_token(subject=user.id))


@router.get("/me", response_model=ProviderProfileRead)
def read_provider_profile(current_user: ProviderUser, db: DBSession) -> ProviderProfileRead:
    return AuthService.get_provider_profile(db=db, user_id=current_user.id)


@router.get("/categories", response_model=ProviderCategoriesRead)
def read_provider_categories(
    current_user: ProviderUser,
    db: DBSession,
) -> ProviderCategoriesRead:
    profile = _provider_profile_for_user(db, current_user)
    return ProviderCategoriesRead(
        category_slugs=CategoryService.get_provider_category_slugs(
            db,
            provider_profile_id=profile.id,
        )
    )


@router.put("/categories", response_model=ProviderCategoriesRead)
def update_provider_categories(
    payload: ProviderCategoriesUpdate,
    current_user: ProviderUser,
    db: DBSession,
) -> ProviderCategoriesRead:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_not_rejected(profile)
    return ProviderCategoriesRead(
        category_slugs=CategoryService.set_provider_category_slugs(
            db,
            provider_profile_id=profile.id,
            category_slugs=payload.category_slugs,
        )
    )


@router.get("/bookings", response_model=list[BookingRead])
def read_provider_bookings(
    current_user: ProviderUser,
    db: DBSession,
    booking_status: Annotated[
        BookingStatus,
        Query(alias="status"),
    ] = BookingStatus.PENDING,
) -> list[BookingRead]:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_approved(profile)
    return BookingService.list_provider_bookings(
        db,
        provider_user=current_user,
        booking_status=booking_status,
    )


@router.patch("/bookings/{booking_id}/status", response_model=BookingRead)
def update_provider_booking_status(
    booking_id: int,
    payload: BookingStatusUpdate,
    current_user: ProviderUser,
    db: DBSession,
) -> BookingRead:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_approved(profile)
    return BookingService.update_provider_booking_status(
        db,
        provider_user=current_user,
        booking_id=booking_id,
        booking_status=payload.status,
    )


@router.patch("/me", response_model=ProviderProfileRead)
def update_provider_profile(
    payload: ProviderProfileUpdate,
    current_user: ProviderUser,
    db: DBSession,
) -> ProviderProfileRead:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_approved(profile)
    return ProviderService.update_profile(
        db,
        user=current_user,
        profile=profile,
        payload=payload,
    )


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_provider_password(
    payload: ProviderPasswordUpdate,
    current_user: ProviderUser,
    db: DBSession,
) -> None:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_approved(profile)
    ProviderService.change_password(db, user=current_user, payload=payload)


@router.post(
    "/document-change-requests",
    response_model=list[ProviderDocumentChangeRead],
    status_code=status.HTTP_201_CREATED,
)
def create_provider_document_change_requests(
    current_user: ProviderUser,
    db: DBSession,
    aadhaar_front: Annotated[
        UploadFile | None,
        File(alias="aadhaarFront"),
    ] = None,
    aadhaar_back: Annotated[
        UploadFile | None,
        File(alias="aadhaarBack"),
    ] = None,
    payment_bill: Annotated[
        UploadFile | None,
        File(alias="paymentBill"),
    ] = None,
    electricity_bill: Annotated[
        UploadFile | None,
        File(alias="electricityBill"),
    ] = None,
) -> list[ProviderDocumentChangeRead]:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_approved(profile)
    requested_documents = [
        (ProviderDocumentType.AADHAAR_FRONT, aadhaar_front, "aadhaar-front-change"),
        (ProviderDocumentType.AADHAAR_BACK, aadhaar_back, "aadhaar-back-change"),
        (ProviderDocumentType.PAYMENT_BILL, payment_bill, "payment-bill-change"),
        (
            ProviderDocumentType.ELECTRICITY_BILL,
            electricity_bill,
            "electricity-bill-change",
        ),
    ]
    if all(file is None for _, file, _ in requested_documents):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Upload at least one document",
        )

    requests = []
    for document_type, file, document_name in requested_documents:
        if file is None:
            continue

        document_path = UploadService.save_provider_document(
            file=file,
            phone=profile.whatsapp_mobile_number,
            document_name=document_name,
        )
        requests.append(
            ProviderService.create_document_request(
                db,
                provider_profile_id=profile.id,
                document_type=document_type,
                document_path=document_path,
            )
        )
    return requests


@router.get(
    "/document-change-requests",
    response_model=list[ProviderDocumentChangeRead],
)
def read_provider_document_change_requests(
    current_user: ProviderUser,
    db: DBSession,
) -> list[ProviderDocumentChangeRead]:
    profile = _provider_profile_for_user(db, current_user)
    _ensure_approved(profile)
    return ProviderService.list_document_requests(
        db,
        provider_profile_id=profile.id,
    )


@router.websocket("/bookings/ws")
async def provider_bookings_websocket(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db),
) -> None:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        user_id = int(subject) if subject is not None else None
    except (InvalidTokenError, ValueError):
        await websocket.close(code=1008)
        return

    if user_id is None:
        await websocket.close(code=1008)
        return

    user = UserRepository.get_by_id(db, user_id=user_id)
    if user is None or user.role != UserRole.PROVIDER.value:
        await websocket.close(code=1008)
        return

    profile = AuthService.get_provider_profile(db=db, user_id=user.id)
    if profile.verification_status != ProviderVerificationStatus.APPROVED.value:
        await websocket.close(code=1008)
        return
    await provider_booking_notifier.connect(profile.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        provider_booking_notifier.disconnect(profile.id, websocket)
