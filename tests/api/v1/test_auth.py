"""Authentication API tests."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.models.client import Client
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


def test_token_oauth2_form_ok(client: TestClient, db_session: Session) -> None:
    """OAuth2 token endpoint accepts form data and returns token pair."""
    create_admin(db_session, "test-auth-token@example.com", "secret123")

    response = client.post(
        "/api/v1/auth/token",
        data={"username": "test-auth-token@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)
    assert data["access_token"]
    assert data["refresh_token"]


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


def test_register_creates_user_and_client(client: TestClient, db_session: Session) -> None:
    """Register endpoint creates linked client user/profile and returns tokens."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Register User",
            "phone": "+5491111112222",
            "email": "test-register@example.com",
            "password": "NewPass123!",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]

    user = db_session.query(User).filter(User.email == "test-register@example.com").first()
    assert user is not None
    assert user.role == "client"
    assert user.is_active is True

    linked_client = db_session.query(Client).filter(Client.user_id == user.id).first()
    assert linked_client is not None
    assert linked_client.full_name == "Test Register User"
    assert linked_client.phone == "+5491111112222"


def test_register_then_login_with_same_credentials(client: TestClient) -> None:
    """Registered client credentials must work on JSON login endpoint."""
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Register Login",
            "phone": "+5491111113333",
            "email": "TeSt-Reg-Login@example.com",
            "password": "MySafePass123!",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "test-reg-login@example.com", "password": "MySafePass123!"},
    )

    assert login_response.status_code == 200
    data = login_response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)
    assert data["access_token"]
    assert data["refresh_token"]


def test_forgot_password_always_returns_200(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Forgot-password returns generic success regardless of account existence."""
    create_admin(db_session, "test-auth-forgot@example.com", "secret123")
    sent_tokens: list[str] = []

    def fake_send_password_reset_email(to_email: str, token: str) -> None:
        sent_tokens.append(token)

    monkeypatch.setattr("app.api.v1.routers.auth.send_password_reset_email", fake_send_password_reset_email)

    existing_response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "test-auth-forgot@example.com"},
    )
    missing_response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "test-auth-missing@example.com"},
    )

    assert existing_response.status_code == 200
    assert missing_response.status_code == 200
    assert existing_response.json()["detail"] == "If the email exists, a password reset link was sent"
    assert missing_response.json()["detail"] == "If the email exists, a password reset link was sent"
    assert len(sent_tokens) == 1


def test_reset_password_changes_credentials(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset-password updates hash and allows login with new password."""
    create_admin(db_session, "test-auth-reset@example.com", "oldpass123")
    sent_tokens: list[str] = []

    def fake_send_password_reset_email(to_email: str, token: str) -> None:
        sent_tokens.append(token)

    monkeypatch.setattr("app.api.v1.routers.auth.send_password_reset_email", fake_send_password_reset_email)

    forgot_response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "test-auth-reset@example.com"},
    )
    assert forgot_response.status_code == 200
    assert len(sent_tokens) == 1

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": sent_tokens[0], "new_password": "newpass123"},
    )
    assert reset_response.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "test-auth-reset@example.com", "password": "oldpass123"},
    )
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "test-auth-reset@example.com", "password": "newpass123"},
    )

    assert old_login.status_code == 401
    assert new_login.status_code == 200
