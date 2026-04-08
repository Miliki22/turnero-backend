"""Client API tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.user import User
from app.services.auth_service import create_access_token, get_password_hash


def create_user(db: Session, email: str, password: str, role: str = "admin") -> User:
    """Insert a user for authenticated API tests."""
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        role=role,
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


def test_create_client(client: TestClient, db_session: Session) -> None:
    """Create client endpoint returns 201 and persisted data."""
    create_user(db_session, "test-clients-create@example.com", "secret123")
    headers = create_auth_headers(client, "test-clients-create@example.com", "secret123")

    response = client.post(
        "/api/v1/clients",
        headers=headers,
        json={
            "full_name": "Test Client Create",
            "phone": "+5491111110001",
            "email": "client-create@example.com",
            "notes": "Prefiere contacto por WhatsApp",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Test Client Create"
    assert data["phone"] == "+5491111110001"
    assert data["email"] == "client-create@example.com"
    assert data["notes"] == "Prefiere contacto por WhatsApp"
    assert data["is_active"] is True


def test_list_clients_active_only_by_default(client: TestClient, db_session: Session) -> None:
    """List clients excludes inactive rows unless include_inactive is true."""
    create_user(db_session, "test-clients-list@example.com", "secret123")
    headers = create_auth_headers(client, "test-clients-list@example.com", "secret123")

    active_client = Client(full_name="Test Client Active", phone="+5491111110002", is_active=True)
    inactive_client = Client(full_name="Test Client Inactive", phone="+5491111110003", is_active=False)
    db_session.add(active_client)
    db_session.add(inactive_client)
    db_session.commit()

    active_response = client.get("/api/v1/clients", headers=headers)
    assert active_response.status_code == 200
    active_data = active_response.json()
    names = {item["full_name"] for item in active_data}
    assert "Test Client Active" in names
    assert "Test Client Inactive" not in names

    all_response = client.get("/api/v1/clients?include_inactive=true", headers=headers)
    assert all_response.status_code == 200
    all_data = all_response.json()
    all_names = {item["full_name"] for item in all_data}
    assert "Test Client Active" in all_names
    assert "Test Client Inactive" in all_names


def test_update_client(client: TestClient, db_session: Session) -> None:
    """Patch endpoint updates only provided fields."""
    create_user(db_session, "test-clients-update@example.com", "secret123")
    headers = create_auth_headers(client, "test-clients-update@example.com", "secret123")

    existing = Client(
        full_name="Test Client Update",
        phone="+5491111110004",
        email="old-email@example.com",
        notes="Nota inicial",
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.patch(
        f"/api/v1/clients/{existing.id}",
        headers=headers,
        json={"phone": "+5491111119999", "notes": "Nota actualizada"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test Client Update"
    assert data["phone"] == "+5491111119999"
    assert data["email"] == "old-email@example.com"
    assert data["notes"] == "Nota actualizada"


def test_soft_delete_client(client: TestClient, db_session: Session) -> None:
    """Delete endpoint performs a soft-delete and returns 204."""
    create_user(db_session, "test-clients-delete@example.com", "secret123")
    headers = create_auth_headers(client, "test-clients-delete@example.com", "secret123")

    existing = Client(
        full_name="Test Client Delete",
        phone="+5491111110005",
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.delete(f"/api/v1/clients/{existing.id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""

    db_session.refresh(existing)
    assert existing.is_active is False


def test_clients_forbidden_for_non_admin(client: TestClient, db_session: Session) -> None:
    """Non-admin authenticated user gets forbidden in admin routes."""
    user = create_user(
        db_session,
        "test-clients-non-admin@example.com",
        "secret123",
        role="staff",
    )
    token = create_access_token(subject=user.email)

    response = client.get(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
