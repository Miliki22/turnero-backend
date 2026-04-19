"""Google integrations API tests."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.models.user import User
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
