"""Authentication API tests."""

from fastapi.testclient import TestClient
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


def test_login_ok(client: TestClient, db_session: Session) -> None:
    """Login with valid admin credentials returns token pair."""
    create_admin(db_session, "test-auth-ok@example.com", "secret123")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test-auth-ok@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)
    assert data["access_token"]
    assert data["refresh_token"]


def test_login_invalid_password(client: TestClient, db_session: Session) -> None:
    """Login with invalid password returns unauthorized."""
    create_admin(db_session, "test-auth-invalid@example.com", "secret123")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test-auth-invalid@example.com", "password": "badpass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_me_requires_token(client: TestClient) -> None:
    """Protected endpoint rejects missing bearer token."""
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_rejects_refresh_token(client: TestClient, db_session: Session) -> None:
    """Protected endpoint only accepts access token type."""
    create_admin(db_session, "test-auth-refresh@example.com", "secret123")

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "test-auth-refresh@example.com", "password": "secret123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert me_response.status_code == 401
