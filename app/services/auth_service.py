from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.provider_profile import ProviderProfile
from app.models.user import User
from app.models.user import UserRole
from app.repositories.provider_repository import ProviderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.customer import CustomerProfileUpdate, CustomerRegisterRequest
from app.schemas.provider import ProviderRegistrationData
from app.schemas.user import UserCreate


class AuthService:
    @staticmethod
    def normalize_phone(phone: str) -> str:
        return phone.strip()

    @staticmethod
    def register_user(db: Session, payload: UserCreate) -> User:
        existing_user = UserRepository.get_by_email(db, email=str(payload.email))
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

        return UserRepository.create(
            db,
            email=str(payload.email),
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
        )

    @staticmethod
    def register_customer(db: Session, payload: CustomerRegisterRequest) -> User:
        phone = AuthService.normalize_phone(payload.phone)
        existing_user = UserRepository.get_by_phone(db, phone=phone)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this phone number already exists",
            )

        return UserRepository.create(
            db,
            phone=phone,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.name,
            role=UserRole.CUSTOMER,
        )

    @staticmethod
    def ensure_provider_registration_available(
        db: Session,
        payload: ProviderRegistrationData,
    ) -> None:
        phone = AuthService.normalize_phone(payload.whatsapp_mobile_number)
        existing_phone_user = UserRepository.get_by_phone(db, phone=phone)
        if existing_phone_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this phone number already exists",
            )

        existing_email_user = UserRepository.get_by_email(db, email=str(payload.email))
        if existing_email_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

    @staticmethod
    def register_provider(
        db: Session,
        *,
        payload: ProviderRegistrationData,
        aadhaar_front_path: str,
        aadhaar_back_path: str,
        payment_bill_path: str,
        electricity_bill_path: str,
    ) -> User:
        phone = AuthService.normalize_phone(payload.whatsapp_mobile_number)
        AuthService.ensure_provider_registration_available(db=db, payload=payload)

        user = User(
            email=str(payload.email).lower(),
            phone=phone,
            full_name=payload.owner_name,
            hashed_password=get_password_hash(payload.password),
            role=UserRole.PROVIDER.value,
        )
        db.add(user)
        db.flush()

        profile = ProviderProfile(
            user_id=user.id,
            shop_company_name=payload.shop_company_name,
            owner_name=payload.owner_name,
            whatsapp_mobile_number=phone,
            email=str(payload.email).lower(),
            aadhaar_front_path=aadhaar_front_path,
            aadhaar_back_path=aadhaar_back_path,
            payment_bill_path=payment_bill_path,
            electricity_bill_path=electricity_bill_path,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
        db.add(profile)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        user = UserRepository.get_by_email(db, email=email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        return user

    @staticmethod
    def authenticate_phone(
        db: Session,
        *,
        phone: str,
        password: str,
        expected_role: UserRole | None = None,
    ) -> User:
        user = UserRepository.get_by_phone(
            db,
            phone=AuthService.normalize_phone(phone),
        )
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect phone number or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if expected_role is not None and user.role != expected_role.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect phone number or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        return user

    @staticmethod
    def get_provider_profile(db: Session, user_id: int):
        profile = ProviderRepository.get_by_user_id(db, user_id=user_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found",
            )
        return profile

    @staticmethod
    def update_customer_profile(
        db: Session,
        *,
        user: User,
        payload: CustomerProfileUpdate,
    ) -> User:
        phone = AuthService.normalize_phone(payload.phone)
        existing_user = UserRepository.get_by_phone(db, phone=phone)
        if existing_user is not None and existing_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this phone number already exists",
            )

        return UserRepository.update_customer_profile(
            db,
            user=user,
            full_name=payload.name,
            phone=phone,
        )
