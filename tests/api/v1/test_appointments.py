"""Appointment API tests."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.models.user import User
from app.services.auth_service import get_password_hash

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def _next_weekday_at(weekday: int, hour: int, minute: int) -> datetime:
    """Return next datetime in AR timezone for a given weekday and time."""
    now = datetime.now(AR_TZ)
    days_ahead = (weekday - now.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    target = now + timedelta(days=days_ahead)
    return target.replace(hour=hour, minute=minute, second=0, microsecond=0)


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


def create_service(db: Session, name: str, duration_minutes: int = 60) -> Service:
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
    db_service = create_service(db_session, "Service Appointment Create", duration_minutes=60)
    start_at = _next_weekday_at(weekday=0, hour=10, minute=0)

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
    response_end_at = datetime.fromisoformat(data["end_at"])
    assert response_start_at.astimezone(AR_TZ) == start_at
    assert response_end_at.astimezone(AR_TZ) == start_at + timedelta(minutes=60)
    assert data["status"] == "scheduled"
    assert data["is_active"] is True


def test_create_appointment_overlapping_returns_409(client: TestClient, db_session: Session) -> None:
    """Create overlapping appointment returns conflict."""
    create_admin(db_session, "test-appointments-overlap@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-overlap@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Overlap")
    db_service = create_service(db_session, "Service Appointment Overlap", duration_minutes=60)
    start_at = _next_weekday_at(weekday=1, hour=11, minute=0)
    existing = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
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


def test_appointment_without_15_min_buffer_returns_409(client: TestClient, db_session: Session) -> None:
    """A new appointment starting exactly at previous end must fail due to buffer."""
    create_admin(db_session, "test-appointments-buffer-conflict@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-buffer-conflict@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Buffer Conflict")
    db_service = create_service(db_session, "Service Appointment Buffer Conflict", duration_minutes=60)
    start_at = _next_weekday_at(weekday=2, hour=10, minute=0)
    existing = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
        status="scheduled",
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": (start_at + timedelta(minutes=60)).isoformat(),
            "end_at": (start_at + timedelta(minutes=120)).isoformat(),
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Appointment overlaps with an existing scheduled appointment"


def test_appointment_starting_15_min_after_end_is_ok(client: TestClient, db_session: Session) -> None:
    """A new appointment starting exactly 15 minutes after previous end is allowed."""
    create_admin(db_session, "test-appointments-buffer-ok@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-buffer-ok@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Buffer OK")
    db_service = create_service(db_session, "Service Appointment Buffer OK", duration_minutes=60)
    start_at = _next_weekday_at(weekday=3, hour=10, minute=0)
    existing = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
        status="scheduled",
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": (start_at + timedelta(minutes=75)).isoformat(),
            "end_at": (start_at + timedelta(minutes=135)).isoformat(),
        },
    )

    assert response.status_code == 201


def test_appointment_outside_business_hours_returns_422(client: TestClient, db_session: Session) -> None:
    """Appointment outside business hours returns 422."""
    create_admin(db_session, "test-appointments-hours@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-hours@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Hours")
    db_service = create_service(db_session, "Service Appointment Hours", duration_minutes=60)
    start_at = _next_weekday_at(weekday=4, hour=8, minute=30)
    end_at = start_at + timedelta(minutes=60)

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Appointment must be within business hours (09:00-19:00)"


def test_appointment_on_saturday_returns_422(client: TestClient, db_session: Session) -> None:
    """Appointment on Saturday returns 422 without override."""
    create_admin(db_session, "test-appointments-saturday@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-saturday@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Saturday")
    db_service = create_service(db_session, "Service Appointment Saturday", duration_minutes=60)
    saturday_start = _next_weekday_at(weekday=5, hour=10, minute=0)

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": saturday_start.isoformat(),
            "end_at": (saturday_start + timedelta(minutes=60)).isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Appointments are only allowed Monday to Friday"


def test_appointment_on_saturday_with_override_is_ok(client: TestClient, db_session: Session) -> None:
    """Appointment on Saturday is allowed when override_schedule=true."""
    create_admin(db_session, "test-appointments-saturday-override@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-saturday-override@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Saturday Override")
    db_service = create_service(db_session, "Service Appointment Saturday Override", duration_minutes=60)
    saturday_start = _next_weekday_at(weekday=5, hour=10, minute=0)

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": saturday_start.isoformat(),
            "end_at": (saturday_start + timedelta(minutes=60)).isoformat(),
            "override_schedule": True,
        },
    )

    assert response.status_code == 201


def test_appointment_with_invalid_duration_returns_422(client: TestClient, db_session: Session) -> None:
    """Appointment with a non-allowed duration returns 422."""
    create_admin(db_session, "test-appointments-duration@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-duration@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment Duration")
    db_service = create_service(db_session, "Service Appointment Duration", duration_minutes=60)
    start_at = _next_weekday_at(weekday=0, hour=11, minute=0)

    response = client.post(
        "/api/v1/appointments",
        headers=auth_headers,
        json={
            "client_id": db_client.id,
            "service_id": db_service.id,
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(minutes=45)).isoformat(),
            "override_schedule": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Duration must be one of: 60, 90, 120 minutes"


def test_list_appointments(client: TestClient, db_session: Session) -> None:
    """List appointments endpoint returns active appointments."""
    create_admin(db_session, "test-appointments-list@example.com", "secret123")
    auth_headers = create_auth_headers(client, "test-appointments-list@example.com", "secret123")
    db_client = create_client(db_session, "Test Client Appointment List")
    db_service = create_service(db_session, "Service Appointment List", duration_minutes=60)
    start_at = _next_weekday_at(weekday=1, hour=12, minute=0)
    appointment = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
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
    db_service = create_service(db_session, "Service Appointment Update", duration_minutes=60)
    start_at = _next_weekday_at(weekday=2, hour=13, minute=0)
    appointment = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
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
    db_service = create_service(db_session, "Service Appointment Delete", duration_minutes=60)
    start_at = _next_weekday_at(weekday=3, hour=14, minute=0)
    appointment = Appointment(
        client_id=db_client.id,
        service_id=db_service.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
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
