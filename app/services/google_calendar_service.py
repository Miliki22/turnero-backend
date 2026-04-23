"""Google OAuth + Calendar sync service helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.google_integration import GoogleIntegration
from app.models.service import Service
from app.models.user import User

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URI_DEFAULT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _load_client_secrets() -> dict[str, Any]:
    """Load Google OAuth client secrets JSON."""
    path = Path(settings.google_oauth_client_secrets_file)
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    if "web" in data and isinstance(data["web"], dict):
        return data["web"]
    if "installed" in data and isinstance(data["installed"], dict):
        return data["installed"]
    return data


def _token_exchange_payload(code: str) -> dict[str, Any]:
    secrets = _load_client_secrets()
    return {
        "code": code,
        "client_id": secrets["client_id"],
        "client_secret": secrets["client_secret"],
        "redirect_uri": settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }


def _token_refresh_payload(refresh_token: str) -> dict[str, Any]:
    secrets = _load_client_secrets()
    return {
        "refresh_token": refresh_token,
        "client_id": secrets["client_id"],
        "client_secret": secrets["client_secret"],
        "grant_type": "refresh_token",
    }


def _create_oauth_state_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "token_type": "google_oauth_state",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_oauth_state_token(state: str) -> int:
    try:
        payload: dict[str, Any] = jwt.decode(
            state,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid state") from exc

    if payload.get("token_type") != "google_oauth_state":
        raise ValueError("Invalid state")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise ValueError("Invalid state")
    return int(sub)


def build_google_auth_url(user_id: int) -> str:
    """Build Google OAuth authorization URL for admin connect flow."""
    secrets = _load_client_secrets()
    auth_uri = secrets.get("auth_uri", GOOGLE_AUTH_URI_DEFAULT)
    query = urlencode(
        {
            "client_id": secrets["client_id"],
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_CALENDAR_EVENTS_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": _create_oauth_state_token(user_id=user_id),
            "include_granted_scopes": "true",
        }
    )
    return f"{auth_uri}?{query}"


def exchange_code_and_store_tokens(db: Session, *, code: str, state: str) -> GoogleIntegration:
    """Exchange auth code, then persist Google tokens for given admin user."""
    user_id = _decode_oauth_state_token(state)
    user = db.query(User).filter(User.id == user_id, User.role == "admin", User.is_active.is_(True)).first()
    if user is None:
        raise ValueError("Invalid state")

    secrets = _load_client_secrets()
    token_uri = secrets.get("token_uri", GOOGLE_TOKEN_URI_DEFAULT)
    response = httpx.post(token_uri, data=_token_exchange_payload(code=code), timeout=20)
    response.raise_for_status()
    token_data: dict[str, Any] = response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in", 3600))
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("Missing access_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        existing = db.query(GoogleIntegration).filter(GoogleIntegration.user_id == user.id).first()
        refresh_token = existing.refresh_token if existing is not None else ""
    if not refresh_token:
        raise ValueError("Missing refresh_token")

    integration = db.query(GoogleIntegration).filter(GoogleIntegration.user_id == user.id).first()
    if integration is None:
        integration = GoogleIntegration(
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            calendar_id=settings.google_calendar_id or "primary",
            email=user.email,
        )
        db.add(integration)
    else:
        integration.access_token = access_token
        integration.refresh_token = refresh_token
        integration.expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        integration.calendar_id = settings.google_calendar_id or integration.calendar_id
        integration.email = user.email
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return integration


def get_integration_status(db: Session, admin_user_id: int) -> dict[str, Any]:
    """Return Google integration status for admin user."""
    integration = (
        db.query(GoogleIntegration)
        .filter(GoogleIntegration.user_id == admin_user_id)
        .first()
    )
    if integration is None:
        return {"connected": False, "calendar_id": settings.google_calendar_id or "primary", "email": None}
    return {
        "connected": True,
        "calendar_id": settings.google_calendar_id or integration.calendar_id or "primary",
        "email": integration.email,
    }


def disconnect_google_integration(db: Session, admin_user_id: int) -> None:
    """Delete persisted Google integration for admin user."""
    integration = (
        db.query(GoogleIntegration)
        .filter(GoogleIntegration.user_id == admin_user_id)
        .first()
    )
    if integration is not None:
        db.delete(integration)
        db.commit()


def get_connected_admin_integration(db: Session) -> GoogleIntegration | None:
    """Return first active admin integration for calendar sync."""
    return (
        db.query(GoogleIntegration)
        .join(User, User.id == GoogleIntegration.user_id)
        .filter(User.role == "admin", User.is_active.is_(True))
        .order_by(GoogleIntegration.id.asc())
        .first()
    )


class GoogleCalendarClient:
    """Google Calendar REST client with automatic token refresh."""

    def __init__(self, db: Session, integration: GoogleIntegration):
        self.db = db
        self.integration = integration

    def _refresh_if_needed(self) -> None:
        if self.integration.expiry > datetime.now(timezone.utc) + timedelta(seconds=30):
            return
        self._refresh_access_token()

    def _refresh_access_token(self) -> None:
        secrets = _load_client_secrets()
        token_uri = secrets.get("token_uri", GOOGLE_TOKEN_URI_DEFAULT)
        response = httpx.post(
            token_uri,
            data=_token_refresh_payload(refresh_token=self.integration.refresh_token),
            timeout=20,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Missing access_token on refresh")

        self.integration.access_token = access_token
        self.integration.expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self.db.add(self.integration)
        self.db.commit()
        self.db.refresh(self.integration)

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        self._refresh_if_needed()
        headers = {"Authorization": f"Bearer {self.integration.access_token}"}
        response = httpx.request(method, path, headers=headers, json=json_body, timeout=20)
        if response.status_code == 401:
            self._refresh_access_token()
            headers = {"Authorization": f"Bearer {self.integration.access_token}"}
            response = httpx.request(method, path, headers=headers, json=json_body, timeout=20)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def _resolve_calendar_id(self, calendar_id: str | None = None) -> str:
        """Resolve calendar target, preferring configured env calendar id."""
        return calendar_id or settings.google_calendar_id or self.integration.calendar_id or "primary"

    def create_event(self, event_payload: dict[str, Any], *, calendar_id: str | None = None) -> str:
        target_calendar_id = quote(self._resolve_calendar_id(calendar_id=calendar_id), safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{target_calendar_id}/events"
        data = self._request("POST", url, json_body=event_payload) or {}
        event_id = data.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Google event id missing")
        return event_id

    def update_event(
        self,
        google_event_id: str,
        event_payload: dict[str, Any],
        *,
        calendar_id: str | None = None,
    ) -> None:
        target_calendar_id = quote(self._resolve_calendar_id(calendar_id=calendar_id), safe="")
        event_id = quote(google_event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{target_calendar_id}/events/{event_id}"
        self._request("PATCH", url, json_body=event_payload)

    def delete_event(self, google_event_id: str, *, calendar_id: str | None = None) -> None:
        target_calendar_id = quote(self._resolve_calendar_id(calendar_id=calendar_id), safe="")
        event_id = quote(google_event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{target_calendar_id}/events/{event_id}"
        self._request("DELETE", url)


def get_google_calendar_client(db: Session, integration: GoogleIntegration) -> GoogleCalendarClient:
    """Factory to create Google calendar client (mockable in tests)."""
    return GoogleCalendarClient(db=db, integration=integration)


def _build_appointment_event_payload(db: Session, appointment: Appointment) -> dict[str, Any] | None:
    """Build Google Calendar event payload from an appointment."""
    client = db.query(Client).filter(Client.id == appointment.client_id).first()
    service = db.query(Service).filter(Service.id == appointment.service_id).first()
    if client is None or service is None:
        return None

    return {
        "summary": f"{service.name} - {client.full_name}",
        "description": f"Cliente: {client.full_name}\nServicio: {service.name}",
        "start": {"dateTime": appointment.start_at.isoformat()},
        "end": {"dateTime": appointment.end_at.isoformat()},
    }


def sync_appointments_to_google(
    db: Session,
    *,
    days_ahead: int = 90,
    include_past_days: int = 0,
) -> dict[str, int]:
    """Backfill appointments into Google Calendar for a bounded date window."""
    integration = get_connected_admin_integration(db=db)
    if integration is None:
        raise ValueError("Google integration is not connected")

    client = get_google_calendar_client(db=db, integration=integration)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=include_past_days)
    window_end = now + timedelta(days=days_ahead)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.start_at >= window_start,
            Appointment.start_at <= window_end,
        )
        .order_by(Appointment.start_at.asc(), Appointment.id.asc())
        .all()
    )

    counters = {
        "scanned": len(appointments),
        "created": 0,
        "skipped_already_linked": 0,
        "skipped_not_eligible": 0,
        "errors": 0,
    }

    for appointment in appointments:
        if appointment.status != "scheduled" or not appointment.is_active:
            counters["skipped_not_eligible"] += 1
            continue

        if appointment.google_event_id:
            counters["skipped_already_linked"] += 1
            continue

        event_payload = _build_appointment_event_payload(db=db, appointment=appointment)
        if event_payload is None:
            counters["skipped_not_eligible"] += 1
            continue

        try:
            event_id = client.create_event(event_payload, calendar_id=settings.google_calendar_id or None)
            appointment.google_event_id = event_id
            db.add(appointment)
            db.commit()
            counters["created"] += 1
        except Exception:
            db.rollback()
            counters["errors"] += 1
            logger.warning(
                "Failed to backfill Google event for appointment id=%s",
                appointment.id,
                exc_info=True,
            )

    return counters


def cleanup_google_appointments(
    db: Session,
    *,
    days_ahead: int = 365,
    include_past_days: int = 30,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Cleanup legacy Google events and optionally reset local google_event_id links."""
    integration = get_connected_admin_integration(db=db)
    if integration is None:
        raise ValueError("Google integration is not connected")

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=include_past_days)
    window_end = now + timedelta(days=days_ahead)
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.start_at >= window_start,
            Appointment.start_at <= window_end,
            Appointment.google_event_id.is_not(None),
        )
        .order_by(Appointment.start_at.asc(), Appointment.id.asc())
        .all()
    )

    result: dict[str, Any] = {
        "scanned": len(appointments),
        "deleted": 0,
        "missing_in_google": 0,
        "reset_in_db": 0,
        "errors": 0,
        "sample_appointment_ids": [appointment.id for appointment in appointments[:5]],
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    google_client = get_google_calendar_client(db=db, integration=integration)
    for appointment in appointments:
        if not appointment.google_event_id:
            continue

        try:
            google_client.delete_event(appointment.google_event_id, calendar_id="primary")
            result["deleted"] += 1
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result["missing_in_google"] += 1
            else:
                result["errors"] += 1
                logger.warning(
                    "Failed to cleanup Google event id=%s for appointment id=%s",
                    appointment.google_event_id,
                    appointment.id,
                    exc_info=True,
                )
                continue
        except Exception:
            result["errors"] += 1
            logger.warning(
                "Failed to cleanup Google event id=%s for appointment id=%s",
                appointment.google_event_id,
                appointment.id,
                exc_info=True,
            )
            continue

        appointment.google_event_id = None
        db.add(appointment)
        db.commit()
        result["reset_in_db"] += 1

    return result
