"""Availability API tests."""

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


def create_linked_client(db: Session, full_name: str, email: str) -> Client:
    """Create a client row linked to a dedicated user."""
    user = create_user(db, email=email, password="secret123", role="client")
    client = Client(
        user_id=user.id,
        full_name=full_name,
        phone="+5491111110000",
        email=email,
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def create_service(db: Session, name: str, duration_minutes: int = 60) -> Service:
    """Create a service row."""
    service = Service(
        name=name,
        duration_minutes=duration_minutes,
        is_active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def test_availability_returns_slots_for_service(client: TestClient, db_session: Session) -> None:
    """Availability endpoint returns slots for active service."""
    create_user(db_session, "test-availability-admin@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-availability-admin@example.com", "secret123")
    service = create_service(db_session, "Service Availability", duration_minutes=60)

    response = client.get(
        f"/api/v1/availability?service_id={service.id}&days_ahead=7&include_past_days=0",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert {"start_at", "end_at", "status"} <= set(data[0].keys())
    assert data[0]["status"] in {"available", "busy"}


def test_availability_marks_busy_slot(client: TestClient, db_session: Session) -> None:
    """Slot is marked busy when it overlaps an existing scheduled appointment."""
    create_user(db_session, "test-availability-busy-admin@example.com", "secret123", role="admin")
    headers = create_auth_headers(client, "test-availability-busy-admin@example.com", "secret123")
    linked_client = create_linked_client(db_session, "Test Availability Client", "test-availability-client@example.com")
    service = create_service(db_session, "Service Availability Busy", duration_minutes=60)
    busy_start = _next_weekday_at(weekday=0, hour=10, minute=0)
    appointment = Appointment(
        client_id=linked_client.id,
        service_id=service.id,
        start_at=busy_start,
        end_at=busy_start + timedelta(minutes=60),
        status="scheduled",
        is_active=True,
    )
    db_session.add(appointment)
    db_session.commit()

    response = client.get(
        f"/api/v1/availability?service_id={service.id}&days_ahead=14&include_past_days=0",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    busy_start_iso = busy_start.isoformat()
    target_slot = next((item for item in data if item["start_at"] == busy_start_iso), None)
    assert target_slot is not None
    assert target_slot["status"] == "busy"


def test_availability_requires_auth(client: TestClient, db_session: Session) -> None:
    """Availability endpoint requires authentication."""
    service = create_service(db_session, "Service Availability No Auth", duration_minutes=60)

    response = client.get(f"/api/v1/availability?service_id={service.id}")

    assert response.status_code == 401
