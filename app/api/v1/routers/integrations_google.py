"""Google integration routes (admin-only)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.google_calendar_service import (
    build_google_auth_url,
    disconnect_google_integration,
    exchange_code_and_store_tokens,
    get_integration_status,
)

router = APIRouter(prefix="/integrations/google", tags=["integrations-google"])


@router.get("/connect")
def connect_google(
    current_user: User = Depends(require_admin_user),
) -> dict[str, str]:
    """Return Google OAuth authorization URL."""
    try:
        auth_url = build_google_auth_url(user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured",
        ) from exc
    return {"auth_url": auth_url}


@router.get("/callback")
def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Exchange OAuth code and redirect to frontend integrations settings page."""
    try:
        exchange_code_and_store_tokens(db=db, code=code, state=state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth callback failed",
        ) from exc

    redirect_url = f"{settings.frontend_url.rstrip('/')}/settings/integrations?google=connected"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/status")
def google_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> dict[str, object]:
    """Return Google integration status for admin user."""
    return get_integration_status(db=db, admin_user_id=current_user.id)


@router.post("/disconnect")
def google_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> dict[str, str]:
    """Disconnect Google integration for admin user."""
    disconnect_google_integration(db=db, admin_user_id=current_user.id)
    return {"detail": "Disconnected"}
