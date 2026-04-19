"""Authentication service helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password."""
    return pwd_context.hash(password)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Authenticate an active user by email and password."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def _create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    """Create a signed JWT token with explicit token type."""
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "token_type": token_type,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str) -> str:
    """Create a JWT access token for a subject."""
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(subject=subject, expires_delta=expires_delta, token_type="access")


def create_refresh_token(subject: str) -> str:
    """Create a JWT refresh token for a subject."""
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    return _create_token(subject=subject, expires_delta=expires_delta, token_type="refresh")


def create_password_reset_token(user_id: int) -> str:
    """Create a short-lived JWT password reset token for a user."""
    expires_delta = timedelta(minutes=settings.password_reset_token_expire_minutes)
    return _create_token(subject=str(user_id), expires_delta=expires_delta, token_type="password_reset")


def verify_password_reset_token(token: str) -> int | None:
    """Decode and validate password reset token payload."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError:
        return None

    if payload.get("token_type") != "password_reset":
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        return None
    return int(subject)
