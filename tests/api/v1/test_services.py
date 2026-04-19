"""Service API tests."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.service import Service
from app.models.user import User
from app.services.auth_service import get_password_hash


def create_user(db: Session, email: str, password: str, role: str = "admin") -> User:
    """Insert an active user for tests."""
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


def test_create_service(client: TestClient, db_session: Session) -> None:
    """Create service endpoint returns 201 and persisted data for admin."""
    create_user(db_session, "test-services-create@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-services-create@example.com", "secret123")

    response = client.post(
        "/api/v1/services",
        headers=headers,
        json={
            "name": "Corte de pelo",
            "description": "Corte clásico",
            "duration_minutes": 45,
            "price": "12000.50",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Corte de pelo"
    assert data["description"] == "Corte clásico"
    assert data["duration_minutes"] == 45
    assert data["price"] == "12000.50"
    assert data["is_active"] is True


def test_non_admin_cannot_create_service(client: TestClient, db_session: Session) -> None:
    """Non-admin users receive 403 when trying to create a service."""
    create_user(db_session, "test-services-create-staff@example.com", "secret123", role="staff")
    headers = create_auth_headers(client, "test-services-create-staff@example.com", "secret123")

    response = client.post(
        "/api/v1/services",
        headers=headers,
        json={
            "name": "No permitido",
            "description": "Intento staff",
            "duration_minutes": 30,
            "price": "1000.00",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_list_services_active_only_by_default(client: TestClient, db_session: Session) -> None:
    """List services excludes inactive rows unless include_inactive is true."""
    create_user(db_session, "test-services-list@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-services-list@example.com", "secret123")

    active_service = Service(
        name="Service Active",
        description="Activo",
        duration_minutes=30,
        price=Decimal("1000.00"),
        is_active=True,
    )
    inactive_service = Service(
        name="Service Inactive",
        description="Inactivo",
        duration_minutes=60,
        price=Decimal("2000.00"),
        is_active=False,
    )
    db_session.add(active_service)
    db_session.add(inactive_service)
    db_session.commit()

    active_response = client.get("/api/v1/services", headers=headers)
    assert active_response.status_code == 200
    names = {item["name"] for item in active_response.json()}
    assert "Service Active" in names
    assert "Service Inactive" not in names

    all_response = client.get("/api/v1/services?include_inactive=true", headers=headers)
    assert all_response.status_code == 200
    all_names = {item["name"] for item in all_response.json()}
    assert "Service Active" in all_names
    assert "Service Inactive" in all_names


def test_client_can_list_services(client: TestClient, db_session: Session) -> None:
    """Client users can read services."""
    create_user(db_session, "test-services-list-client@example.com", "secret123", role="client")
    headers = create_auth_headers(client, "test-services-list-client@example.com", "secret123")

    service = Service(
        name="Service Readable",
        description="Visible para client",
        duration_minutes=40,
        price=Decimal("1500.00"),
        is_active=True,
    )
    db_session.add(service)
    db_session.commit()

    response = client.get("/api/v1/services", headers=headers)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "Service Readable" in names


def test_update_service(client: TestClient, db_session: Session) -> None:
    """Patch endpoint updates only provided fields for admin."""
    create_user(db_session, "test-services-update@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-services-update@example.com", "secret123")

    existing = Service(
        name="Service Update",
        description="Desc inicial",
        duration_minutes=50,
        price=Decimal("1500.00"),
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.patch(
        f"/api/v1/services/{existing.id}",
        headers=headers,
        json={"duration_minutes": 70, "price": "1999.99"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Service Update"
    assert data["description"] == "Desc inicial"
    assert data["duration_minutes"] == 70
    assert data["price"] == "1999.99"


def test_non_admin_cannot_update_service(client: TestClient, db_session: Session) -> None:
    """Non-admin users receive 403 when trying to update a service."""
    create_user(db_session, "test-services-update-staff@example.com", "secret123", role="staff")
    headers = create_auth_headers(client, "test-services-update-staff@example.com", "secret123")

    existing = Service(
        name="Service Update Forbidden",
        description="Desc",
        duration_minutes=20,
        price=Decimal("500.00"),
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.patch(
        f"/api/v1/services/{existing.id}",
        headers=headers,
        json={"duration_minutes": 25},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_soft_delete_service(client: TestClient, db_session: Session) -> None:
    """Delete endpoint performs a soft-delete and returns 204 for admin."""
    create_user(db_session, "test-services-delete@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-services-delete@example.com", "secret123")

    existing = Service(
        name="Service Delete",
        duration_minutes=25,
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.delete(f"/api/v1/services/{existing.id}", headers=headers)

    assert response.status_code == 204
    assert response.content == b""

    db_session.refresh(existing)
    assert existing.is_active is False


def test_non_admin_cannot_delete_service(client: TestClient, db_session: Session) -> None:
    """Non-admin users receive 403 when trying to delete a service."""
    create_user(db_session, "test-services-delete-staff@example.com", "secret123", role="staff")
    headers = create_auth_headers(client, "test-services-delete-staff@example.com", "secret123")

    existing = Service(
        name="Service Delete Forbidden",
        duration_minutes=30,
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.delete(f"/api/v1/services/{existing.id}", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"
