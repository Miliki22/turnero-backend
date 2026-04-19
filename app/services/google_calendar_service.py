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
from app.models.google_integration import GoogleIntegration
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
        "calendar_id": integration.calendar_id,
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

    def create_event(self, event_payload: dict[str, Any]) -> str:
        calendar_id = quote(self.integration.calendar_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        data = self._request("POST", url, json_body=event_payload) or {}
        event_id = data.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Google event id missing")
        return event_id

    def update_event(self, google_event_id: str, event_payload: dict[str, Any]) -> None:
        calendar_id = quote(self.integration.calendar_id, safe="")
        event_id = quote(google_event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
        self._request("PATCH", url, json_body=event_payload)

    def delete_event(self, google_event_id: str) -> None:
        calendar_id = quote(self.integration.calendar_id, safe="")
        event_id = quote(google_event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"
        self._request("DELETE", url)


def get_google_calendar_client(db: Session, integration: GoogleIntegration) -> GoogleCalendarClient:
    """Factory to create Google calendar client (mockable in tests)."""
    return GoogleCalendarClient(db=db, integration=integration)
