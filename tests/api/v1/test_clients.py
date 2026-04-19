"""Client API tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.user import User
from app.services.auth_service import get_password_hash


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


def create_linked_client(db: Session, full_name: str, email: str, is_active: bool = True) -> Client:
    """Create a client row linked to a dedicated user."""
    user = create_user(db, email=email, password="secret123", role="client")
    client = Client(
        user_id=user.id,
        full_name=full_name,
        phone="+5491111110000",
        email=email,
        is_active=is_active,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def test_create_client(client: TestClient, db_session: Session) -> None:
    """Create client endpoint returns 201 and persisted data for admin."""
    create_user(db_session, "test-clients-create@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-clients-create@example.com", "secret123")

    response = client.post(
        "/api/v1/clients",
        headers=headers,
        json={
            "full_name": "Test Client Create",
            "phone": "+5491111110001",
            "email": "test-client-create@example.com",
            "notes": "Prefiere contacto por WhatsApp",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Test Client Create"
    assert data["phone"] == "+5491111110001"
    assert data["email"] == "test-client-create@example.com"
    assert data["notes"] == "Prefiere contacto por WhatsApp"
    assert data["is_active"] is True


def test_non_admin_cannot_create_client(client: TestClient, db_session: Session) -> None:
    """Non-admin users receive 403 when trying to create a client."""
    create_user(db_session, "test-clients-create-staff@example.com", "secret123", role="staff")
    headers = create_auth_headers(client, "test-clients-create-staff@example.com", "secret123")

    response = client.post(
        "/api/v1/clients",
        headers=headers,
        json={
            "full_name": "Test Client Forbidden",
            "phone": "+5491111110100",
            "email": "staff-create@example.com",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_list_clients_active_only_by_default(client: TestClient, db_session: Session) -> None:
    """List clients excludes inactive rows unless include_inactive is true."""
    create_user(db_session, "test-clients-list@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-clients-list@example.com", "secret123")

    create_linked_client(
        db_session,
        full_name="Test Client Active",
        email="test-clients-active@example.com",
        is_active=True,
    )
    create_linked_client(
        db_session,
        full_name="Test Client Inactive",
        email="test-clients-inactive@example.com",
        is_active=False,
    )

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


def test_non_admin_cannot_list_clients(client: TestClient, db_session: Session) -> None:
    """Non-admin authenticated users cannot list clients."""
    create_user(db_session, "test-clients-list-client@example.com", "secret123", role="client")
    headers = create_auth_headers(client, "test-clients-list-client@example.com", "secret123")

    response = client.get("/api/v1/clients", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_update_client(client: TestClient, db_session: Session) -> None:
    """Patch endpoint updates only provided fields for admin."""
    create_user(db_session, "test-clients-update@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-clients-update@example.com", "secret123")

    existing = create_linked_client(
        db_session,
        full_name="Test Client Update",
        email="test-old-email@example.com",
        is_active=True,
    )
    existing.notes = "Nota inicial"
    db_session.add(existing)
    db_session.commit()

    response = client.patch(
        f"/api/v1/clients/{existing.id}",
        headers=headers,
        json={"phone": "+5491111119999", "notes": "Nota actualizada"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test Client Update"
    assert data["phone"] == "+5491111119999"
    assert data["email"] == "test-old-email@example.com"
    assert data["notes"] == "Nota actualizada"


def test_non_admin_cannot_update_client(client: TestClient, db_session: Session) -> None:
    """Non-admin users receive 403 when trying to update a client."""
    create_user(db_session, "test-clients-update-staff@example.com", "secret123", role="staff")
    headers = create_auth_headers(client, "test-clients-update-staff@example.com", "secret123")

    existing = create_linked_client(
        db_session,
        full_name="Test Client Update Forbidden",
        email="test-clients-update-forbidden@example.com",
        is_active=True,
    )

    response = client.patch(
        f"/api/v1/clients/{existing.id}",
        headers=headers,
        json={"notes": "Intento staff"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_soft_delete_client(client: TestClient, db_session: Session) -> None:
    """Delete endpoint performs a soft-delete and returns 204 for admin."""
    create_user(db_session, "test-clients-delete@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-clients-delete@example.com", "secret123")

    existing = create_linked_client(
        db_session,
        full_name="Test Client Delete",
        email="test-clients-delete-linked@example.com",
        is_active=True,
    )

    response = client.delete(f"/api/v1/clients/{existing.id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""

    db_session.refresh(existing)
    assert existing.is_active is False


def test_non_admin_cannot_delete_client(client: TestClient, db_session: Session) -> None:
    """Non-admin users receive 403 when trying to delete a client."""
    create_user(db_session, "test-clients-delete-staff@example.com", "secret123", role="staff")
    headers = create_auth_headers(client, "test-clients-delete-staff@example.com", "secret123")

    existing = create_linked_client(
        db_session,
        full_name="Test Client Delete Forbidden",
        email="test-clients-delete-forbidden@example.com",
        is_active=True,
    )

    response = client.delete(f"/api/v1/clients/{existing.id}", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
