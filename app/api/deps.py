"""Reusable API dependencies."""

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_active_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Decode access token and fetch the current active user."""
    credentials_exception = _credentials_exception()

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        email = payload.get("sub")
        token_type = payload.get("token_type")
    except JWTError as exc:
        raise credentials_exception from exc

    if not isinstance(email, str) or token_type != "access":
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Ensure the authenticated user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


def require_admin_or_client_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Ensure user role is either admin or client."""
    if current_user.role not in {"admin", "client"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


def get_current_user(current_user: User = Depends(require_admin_user)) -> User:
    """Backward-compatible admin-only dependency."""
    return current_user


def get_current_client_or_403(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Client:
    """Resolve authenticated user's client profile or raise 403."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    client = db.query(Client).filter(Client.user_id == current_user.id, Client.is_active.is_(True)).first()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client profile not found",
        )
    return client
