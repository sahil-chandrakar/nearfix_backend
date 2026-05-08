from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.user_phone_history import UserPhoneHistory


class UserRepository:
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> User | None:
        return db.scalar(select(User).where(User.id == user_id))

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email.lower()))

    @staticmethod
    def get_by_phone(db: Session, phone: str) -> User | None:
        return db.scalar(select(User).where(User.phone == phone))

    @staticmethod
    def create(
        db: Session,
        *,
        hashed_password: str,
        email: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
        role: UserRole = UserRole.CUSTOMER,
    ) -> User:
        user = User(
            email=email.lower() if email is not None else None,
            phone=phone,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_customer_profile(
        db: Session,
        *,
        user: User,
        full_name: str,
        phone: str,
    ) -> User:
        if user.phone != phone:
            db.add(
                UserPhoneHistory(
                    user_id=user.id,
                    old_phone=user.phone,
                    new_phone=phone,
                )
            )

        user.full_name = full_name
        user.phone = phone
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list_phone_history(db: Session, *, user_id: int) -> list[UserPhoneHistory]:
        return list(
            db.scalars(
                select(UserPhoneHistory)
                .where(UserPhoneHistory.user_id == user_id)
                .order_by(UserPhoneHistory.changed_at.desc(), UserPhoneHistory.id.desc())
            )
        )

    @staticmethod
    def list_by_role(db: Session, *, role: UserRole, q: str | None = None) -> list[User]:
        statement = select(User).where(User.role == role.value)
        if q:
            like = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    User.full_name.ilike(like),
                    User.phone.ilike(like),
                    User.email.ilike(like),
                )
            )
        return list(db.scalars(statement.order_by(User.created_at.desc(), User.id.desc())))

    @staticmethod
    def update_active(db: Session, *, user: User, is_active: bool) -> User:
        user.is_active = is_active
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_password(db: Session, *, user: User, hashed_password: str) -> User:
        user.hashed_password = hashed_password
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
