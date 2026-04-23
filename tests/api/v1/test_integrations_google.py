"""Google integrations API tests."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.client import Client
from app.models.google_integration import GoogleIntegration
from app.models.service import Service
from app.models.user import User
from app.services.google_calendar_service import GoogleCalendarClient
from app.services.auth_service import get_password_hash


def create_admin(db: Session, email: str, password: str) -> User:
    """Insert an active admin user for tests."""
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    """Return bearer auth headers after login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_client_profile(db: Session, *, email: str, full_name: str) -> Client:
    """Insert a client user and linked profile for tests."""
    user = User(
        email=email,
        password_hash=get_password_hash("secret123"),
        role="client",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = Client(
        user_id=user.id,
        full_name=full_name,
        phone="+5491111111111",
        email=email,
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def create_service(db: Session, *, name: str) -> Service:
    """Insert a service for tests."""
    service = Service(name=name, duration_minutes=60, is_active=True)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def test_google_connect_returns_auth_url(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connect endpoint returns OAuth URL for authenticated admins."""
    create_admin(db_session, "test-google-connect@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-google-connect@example.com", "secret123")

    monkeypatch.setattr(
        "app.api.v1.routers.integrations_google.build_google_auth_url",
        lambda user_id: f"https://accounts.google.com/mock?uid={user_id}",
    )

    response = client.get("/api/v1/integrations/google/connect", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["auth_url"].startswith("https://accounts.google.com/mock")


def test_google_status_returns_connected_flag(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Status endpoint delegates to service and returns integration status."""
    create_admin(db_session, "test-google-status@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-google-status@example.com", "secret123")

    monkeypatch.setattr(
        "app.api.v1.routers.integrations_google.get_integration_status",
        lambda db, admin_user_id: {
            "connected": True,
            "calendar_id": "primary",
            "email": "admin@example.com",
        },
    )

    response = client.get("/api/v1/integrations/google/status", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "connected": True,
        "calendar_id": "primary",
        "email": "admin@example.com",
    }


def test_google_client_create_event_uses_configured_calendar_id(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calendar client must use configured calendar id instead of primary."""
    admin = create_admin(db_session, "test-google-calendar-target@example.com", "secret123")
    integration = GoogleIntegration(
        user_id=admin.id,
        access_token="token",
        refresh_token="refresh",
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        calendar_id="primary",
        email=admin.email,
    )
    db_session.add(integration)
    db_session.commit()
    db_session.refresh(integration)

    captured: dict[str, str] = {}

    class DummyResponse:
        status_code = 200
        content = b'{"id":"evt-123"}'

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"id": "evt-123"}

    def fake_request(method: str, path: str, headers: dict[str, str], json: dict[str, object], timeout: int) -> DummyResponse:
        captured["path"] = path
        return DummyResponse()

    monkeypatch.setattr("app.services.google_calendar_service.settings.google_calendar_id", "experiencia@group.calendar.google.com")
    monkeypatch.setattr("app.services.google_calendar_service.httpx.request", fake_request)

    client = GoogleCalendarClient(db=db_session, integration=integration)
    event_id = client.create_event({"summary": "Test"})

    assert event_id == "evt-123"
    assert "experiencia%40group.calendar.google.com" in captured["path"]
    assert "/calendars/primary/" not in captured["path"]


def test_google_cleanup_dry_run_admin_does_not_modify_db(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dry-run cleanup returns counters and leaves google_event_id untouched."""
    create_admin(db_session, "test-google-cleanup-admin@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-google-cleanup-admin@example.com", "secret123")
    profile = create_client_profile(
        db_session,
        email="test-google-cleanup-client@example.com",
        full_name="Test Cleanup Client",
    )
    service = create_service(db_session, name="Service Cleanup")
    start_at = datetime.now(timezone.utc) + timedelta(days=1)
    appointment = Appointment(
        client_id=profile.id,
        service_id=service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
        status="scheduled",
        is_active=True,
        google_event_id="old-google-event",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    monkeypatch.setattr(
        "app.services.google_calendar_service.get_connected_admin_integration",
        lambda db: object(),
    )

    response = client.post(
        "/api/v1/integrations/google/cleanup?days_ahead=365&include_past_days=30&dry_run=true",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["scanned"] >= 1
    assert data["deleted"] == 0
    assert data["reset_in_db"] == 0
    assert data["errors"] == 0
    assert data["dry_run"] is True

    db_session.refresh(appointment)
    assert appointment.google_event_id == "old-google-event"


def test_google_cleanup_non_admin_returns_403(client: TestClient, db_session: Session) -> None:
    """Cleanup endpoint is forbidden for non-admin users."""
    non_admin = User(
        email="test-google-cleanup-non-admin@example.com",
        password_hash=get_password_hash("secret123"),
        role="client",
        is_active=True,
    )
    db_session.add(non_admin)
    db_session.commit()

    auth_headers = create_auth_headers(client, "test-google-cleanup-non-admin@example.com", "secret123")
    response = client.post("/api/v1/integrations/google/cleanup", headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_google_sync_admin_returns_counters(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync endpoint returns counters for admin users."""
    create_admin(db_session, "test-google-sync-admin@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-google-sync-admin@example.com", "secret123")

    monkeypatch.setattr(
        "app.api.v1.routers.integrations_google.sync_appointments_to_google",
        lambda db, days_ahead, include_past_days: {
            "scanned": 2,
            "created": 2,
            "skipped_already_linked": 0,
            "skipped_not_eligible": 0,
            "errors": 0,
        },
    )

    response = client.post(
        "/api/v1/integrations/google/sync?days_ahead=90&include_past_days=0",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "scanned": 2,
        "created": 2,
        "skipped_already_linked": 0,
        "skipped_not_eligible": 0,
        "errors": 0,
    }


def test_google_sync_non_admin_returns_403(client: TestClient, db_session: Session) -> None:
    """Sync endpoint is forbidden for non-admin users."""
    non_admin_user = User(
        email="test-google-sync-client@example.com",
        password_hash=get_password_hash("secret123"),
        role="client",
        is_active=True,
    )
    db_session.add(non_admin_user)
    db_session.commit()

    auth_headers = create_auth_headers(client, "test-google-sync-client@example.com", "secret123")
    response = client.post("/api/v1/integrations/google/sync", headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
