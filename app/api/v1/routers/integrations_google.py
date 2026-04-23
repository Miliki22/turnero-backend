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
    cleanup_google_appointments,
    disconnect_google_integration,
    exchange_code_and_store_tokens,
    get_integration_status,
    sync_appointments_to_google,
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


@router.post("/sync")
def google_sync(
    days_ahead: int = Query(90, ge=1, le=365),
    include_past_days: int = Query(0, ge=0, le=30),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> dict[str, int]:
    """Backfill existing appointments into Google Calendar."""
    try:
        return sync_appointments_to_google(
            db=db,
            days_ahead=days_ahead,
            include_past_days=include_past_days,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/cleanup")
def google_cleanup(
    days_ahead: int = Query(365, ge=1, le=365),
    include_past_days: int = Query(30, ge=0, le=365),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> dict[str, object]:
    """Cleanup legacy Google events from primary calendar and reset DB links."""
    try:
        return cleanup_google_appointments(
            db=db,
            days_ahead=days_ahead,
            include_past_days=include_past_days,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
