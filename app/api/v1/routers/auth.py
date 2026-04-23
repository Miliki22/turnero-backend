"""Authentication routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    Token,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    get_password_hash,
    verify_password_reset_token,
)
from app.services.email_service import (
    send_password_reset_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Authenticate an active user and return an access/refresh token pair."""
    normalized_email = payload.email.strip().lower()
    user = authenticate_user(db=db, email=normalized_email, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return Token(
        access_token=create_access_token(subject=user.email),
        refresh_token=create_refresh_token(subject=user.email),
    )


@router.post("/token", response_model=Token)
def token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    """OAuth2-compatible password flow endpoint for Swagger Authorize."""
    normalized_email = form_data.username.strip().lower()
    user = authenticate_user(db=db, email=normalized_email, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return Token(
        access_token=create_access_token(subject=user.email),
        refresh_token=create_refresh_token(subject=user.email),
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_active_user)) -> dict[str, str]:
    """Return the authenticated user profile."""
    return {"email": current_user.email, "role": current_user.role}


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Token:
    """Register a new client user and linked client profile."""
    normalized_email = payload.email.strip().lower()
    existing_user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=normalized_email,
        password_hash=get_password_hash(payload.password),
        role="client",
        is_active=True,
    )
    db.add(user)
    db.flush()

    client = Client(
        user_id=user.id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=normalized_email,
        notes=None,
        is_active=True,
    )
    db.add(client)
    db.commit()

    return Token(
        access_token=create_access_token(subject=user.email),
        refresh_token=create_refresh_token(subject=user.email),
    )


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Request a password reset email without revealing account existence."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is not None and user.is_active:
        token = create_password_reset_token(user_id=user.id)
        try:
            send_password_reset_email(to_email=user.email, token=token)
        except Exception:  # pragma: no cover
            logger.exception("Failed to send password reset email")

    return {"detail": "If the email exists, a password reset link was sent"}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Reset user password using a short-lived reset token."""
    user_id = verify_password_reset_token(payload.token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    user.password_hash = get_password_hash(payload.new_password)
    db.add(user)
    db.commit()
    return {"detail": "Password updated"}
