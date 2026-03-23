"""Create or update an initial admin user."""

import argparse

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.services.auth_service import get_password_hash


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Create or update an admin user")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    return parser.parse_args()


def upsert_admin(db: Session, email: str, password: str) -> tuple[User, bool]:
    """Create admin user if missing, otherwise update credentials."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, True

    user.password_hash = get_password_hash(password)
    user.role = "admin"
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user, False


def main() -> None:
    """Run admin bootstrap command."""
    args = parse_args()
    db = SessionLocal()
    try:
        user, created = upsert_admin(db=db, email=args.email, password=args.password)
        action = "Created" if created else "Updated"
        print(f"{action} admin user: {user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
