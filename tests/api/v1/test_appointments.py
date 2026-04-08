"""Appointment API tests."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
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


def create_client(db: Session, full_name: str) -> Client:
    """Insert an active client for tests."""
    client = Client(
        full_name=full_name,
        phone="+5491111111111",
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def create_service(db: Session, name: str, duration_minutes: int = 45) -> Service:
    """Insert an active service for tests."""
    service = Service(
        name=name,
        duration_minutes=duration_minutes,
        is_active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def create_auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    """Return bearer auth headers after login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_appointment_ok(client: TestClient, db_session: Session) -> None:
    """Create appointment endpoint returns 201 and persisted data."""
    create_admin(db_session, "test-appointments-create@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-create@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Create")
    db_service = create_service(db_session, "Service Appointment Create", duration_minutes=50)
    start_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": start_at.isoformat(),
            "notes": "Primer turno",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["client_id"] == db_client.id
    assert data["service_id"] == db_service.id
    response_start_at = datetime.fromisoformat(data["start_at"])
    expected_end_at = start_at + timedelta(minutes=50)
    response_end_at = datetime.fromisoformat(data["end_at"])
    assert response_start_at.astimezone(timezone.utc) == start_at
    assert response_end_at.astimezone(timezone.utc) == expected_end_at
    assert data["status"] == "scheduled"
    assert data["is_active"] is True


def test_create_appointment_overlapping_returns_409(client: TestClient, db_session: Session) -> None:
    """Create overlapping appointment returns conflict."""
    create_admin(db_session, "test-appointments-overlap@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-overlap@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Overlap")
    db_service = create_service(db_session, "Service Appointment Overlap", duration_minutes=45)
    start_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    existing = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=45),
        status="scheduled",
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    overlap_response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": (start_at + timedelta(minutes=30)).isoformat(),
            "end_at": (start_at + timedelta(minutes=90)).isoformat(),
        },
    )

    assert overlap_response.status_code == 409
    assert overlap_response.json()["detail"] == "Appointment overlaps with an existing scheduled appointment"


def test_list_appointments(client: TestClient, db_session: Session) -> None:
    """List appointments endpoint returns active appointments."""
    create_admin(db_session, "test-appointments-list@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-list@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment List")
    db_service = create_service(db_session, "Service Appointment List", duration_minutes=30)
    start_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)
    appointment = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=30),
        status="scheduled",
        is_active=True,
    )
    db_session.add(appointment)
    db_session.commit()

    response = client.get("/api/v1/appointments", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data}
    assert appointment.id in ids


def test_update_appointment(client: TestClient, db_session: Session) -> None:
    """Patch endpoint updates appointment fields."""
    create_admin(db_session, "test-appointments-update@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-update@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Update")
    db_service = create_service(db_session, "Service Appointment Update", duration_minutes=30)
    start_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=4)
    appointment = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=30),
        status="scheduled",
        notes="Antes",
        is_active=True,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    response = client.patch(
        f"/api/v1/appointments/{appointment.id}",
        headers=auth_headers,
        json={"status": "cancelled", "notes": "Reagendado"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["notes"] == "Reagendado"


def test_soft_delete_appointment(client: TestClient, db_session: Session) -> None:
    """Delete endpoint performs a soft-delete and returns 204."""
    create_admin(db_session, "test-appointments-delete@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-delete@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Delete")
    db_service = create_service(db_session, "Service Appointment Delete", duration_minutes=30)
    start_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=5)
    appointment = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=30),
        status="scheduled",
        is_active=True,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    response = client.delete(f"/api/v1/appointments/{appointment.id}", headers=auth_headers)

    assert response.status_code == 204
    assert response.content == b""

    db_session.refresh(appointment)
    assert appointment.is_active is False
