from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.security import get_password_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a NearFix admin user.")
    parser.add_argument("--phone", required=True, help="10-digit admin phone number")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", default="NearFix Admin", help="Admin display name")
    parser.add_argument(
        "--promote-existing",
        action="store_true",
        help="Allow promoting an existing non-admin user with this phone to admin.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phone = args.phone.strip()
    if not phone.isdigit() or len(phone) != 10:
        print("Admin phone must be exactly 10 digits.", file=sys.stderr)
        return 2
    if len(args.password) < 8:
        print("Admin password must be at least 8 characters.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        user = UserRepository.get_by_phone(db, phone=phone)
        if user is not None and user.role != UserRole.ADMIN.value and not args.promote_existing:
            print(
                "A non-admin user already exists with this phone. "
                "Re-run with --promote-existing only if you really want to promote it.",
                file=sys.stderr,
            )
            return 1

        if user is None:
            user = User(
                phone=phone,
                full_name=args.name,
                hashed_password=get_password_hash(args.password),
                role=UserRole.ADMIN.value,
                is_superuser=True,
            )
            db.add(user)
            db.commit()
            print(f"Created admin user {phone}.")
            return 0

        user.full_name = args.name
        user.hashed_password = get_password_hash(args.password)
        user.role = UserRole.ADMIN.value
        user.is_superuser = True
        user.is_active = True
        db.add(user)
        db.commit()
        print(f"Updated admin user {phone}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
