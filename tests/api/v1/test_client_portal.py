"""Client self-service portal API tests."""

from datetime import date, datetime, timedelta
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


def _next_weekday_date(weekday: int) -> date:
    """Return next date for weekday index (Mon=0..Sun=6)."""
    return _next_weekday_at(weekday=weekday, hour=10, minute=0).date()


def create_user(db: Session, email: str, password: str, role: str = "client") -> User:
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


def create_client_profile(db: Session, *, email: str, full_name: str) -> Client:
    """Create a client profile linked to a client user."""
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


def create_service(db: Session, *, name: str, duration_minutes: int = 60) -> Service:
    """Insert active service row."""
    service = Service(name=name, duration_minutes=duration_minutes, is_active=True)
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


def test_client_availability_generates_weekday_slots(client: TestClient, db_session: Session) -> None:
    """Client availability returns slots for a business weekday."""
    create_client_profile(
        db_session,
        email="test-client-availability-weekday@example.com",
        full_name="Test Client Availability Weekday",
    )
    auth_headers = create_auth_headers(client, "test-client-availability-weekday@example.com", "secret123")
    service = create_service(db_session, name="Service Client Availability", duration_minutes=60)
    monday = _next_weekday_date(0)

    response = client.get(
        f"/api/v1/client/availability?service_id={service.id}&range=week&start_date={monday}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    slots = response.json()
    assert len(slots) == 50
    assert slots[0]["status"] in {"available", "occupied"}


def test_client_availability_skips_weekends(client: TestClient, db_session: Session) -> None:
    """Client availability output excludes weekend dates."""
    create_client_profile(
        db_session,
        email="test-client-availability-weekend@example.com",
        full_name="Test Client Availability Weekend",
    )
    auth_headers = create_auth_headers(client, "test-client-availability-weekend@example.com", "secret123")
    service = create_service(db_session, name="Service Client Weekend", duration_minutes=60)
    saturday = _next_weekday_date(5)

    response = client.get(
        f"/api/v1/client/availability?service_id={service.id}&range=week&start_date={saturday}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    slots = response.json()
    assert len(slots) > 0
    for slot in slots:
        slot_weekday = datetime.fromisoformat(slot["start_at"]).weekday()
        assert slot_weekday <= 4


def test_client_availability_marks_occupied(client: TestClient, db_session: Session) -> None:
    """Slots overlapping scheduled appointments are marked occupied."""
    client_profile = create_client_profile(
        db_session,
        email="test-client-availability-occupied@example.com",
        full_name="Test Client Availability Occupied",
    )
    auth_headers = create_auth_headers(client, "test-client-availability-occupied@example.com", "secret123")
    service = create_service(db_session, name="Service Client Occupied", duration_minutes=60)
    monday_start = _next_weekday_at(0, 10, 0)
    db_session.add(
        Appointment(
            client_id=client_profile.id,
            service_id=service.id,
            start_at=monday_start,
            end_at=monday_start + timedelta(minutes=60),
            status="scheduled",
            is_active=True,
        )
    )
    db_session.commit()

    monday = monday_start.date()
    response = client.get(
        f"/api/v1/client/availability?service_id={service.id}&range=week&start_date={monday}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    slots = response.json()
    occupied = [slot for slot in slots if slot["start_at"] == monday_start.isoformat()]
    assert len(occupied) == 1
    assert occupied[0]["status"] == "occupied"


def test_client_create_appointment_ok(client: TestClient, db_session: Session) -> None:
    """Client can create appointment on free business slot."""
    client_profile = create_client_profile(
        db_session,
        email="test-client-create-appointment@example.com",
        full_name="Test Client Create Appointment",
    )
    auth_headers = create_auth_headers(client, "test-client-create-appointment@example.com", "secret123")
    service = create_service(db_session, name="Service Client Create", duration_minutes=60)
    monday_start = _next_weekday_at(0, 11, 0)

    response = client.post(
        "/api/v1/client/appointments",
        headers=auth_headers,
        json={"service_id": service.id, "start_at": monday_start.isoformat()},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == client_profile.id
    assert data["service_id"] == service.id
    assert data["status"] == "scheduled"


def test_client_create_appointment_overlap_returns_409(client: TestClient, db_session: Session) -> None:
    """Client booking returns 409 when slot overlaps an existing appointment."""
    client_profile = create_client_profile(
        db_session,
        email="test-client-create-overlap@example.com",
        full_name="Test Client Create Overlap",
    )
    auth_headers = create_auth_headers(client, "test-client-create-overlap@example.com", "secret123")
    service = create_service(db_session, name="Service Client Overlap", duration_minutes=60)
    monday_start = _next_weekday_at(0, 12, 0)
    db_session.add(
        Appointment(
            client_id=client_profile.id,
            service_id=service.id,
            start_at=monday_start,
            end_at=monday_start + timedelta(minutes=60),
            status="scheduled",
            is_active=True,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/client/appointments",
        headers=auth_headers,
        json={"service_id": service.id, "start_at": monday_start.isoformat()},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Appointment overlaps with an existing scheduled appointment"


def test_client_create_appointment_outside_schedule_returns_400(client: TestClient, db_session: Session) -> None:
    """Client booking outside business hours is rejected with 400."""
    create_client_profile(
        db_session,
        email="test-client-create-hours@example.com",
        full_name="Test Client Create Hours",
    )
    auth_headers = create_auth_headers(client, "test-client-create-hours@example.com", "secret123")
    service = create_service(db_session, name="Service Client Hours", duration_minutes=60)
    monday_early = _next_weekday_at(0, 8, 0)

    response = client.post(
        "/api/v1/client/appointments",
        headers=auth_headers,
        json={"service_id": service.id, "start_at": monday_early.isoformat()},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Appointment must be within business hours (09:00-19:00)"


def test_client_create_appointment_weekend_returns_400(client: TestClient, db_session: Session) -> None:
    """Client booking on weekends is rejected with 400."""
    create_client_profile(
        db_session,
        email="test-client-create-weekend@example.com",
        full_name="Test Client Create Weekend",
    )
    auth_headers = create_auth_headers(client, "test-client-create-weekend@example.com", "secret123")
    service = create_service(db_session, name="Service Client Weekend Create", duration_minutes=60)
    saturday = _next_weekday_at(5, 10, 0)

    response = client.post(
        "/api/v1/client/appointments",
        headers=auth_headers,
        json={"service_id": service.id, "start_at": saturday.isoformat()},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Appointments are only allowed Monday to Friday"


def test_client_get_appointments_returns_only_own(client: TestClient, db_session: Session) -> None:
    """GET /client/appointments returns only authenticated client's appointments."""
    own_client = create_client_profile(
        db_session,
        email="test-client-list-own@example.com",
        full_name="Test Client List Own",
    )
    other_client = create_client_profile(
        db_session,
        email="test-client-list-other@example.com",
        full_name="Test Client List Other",
    )
    headers = create_auth_headers(client, "test-client-list-own@example.com", "secret123")
    service = create_service(db_session, name="Service Client List", duration_minutes=60)
    own_start = _next_weekday_at(0, 10, 0)
    other_start = _next_weekday_at(0, 12, 0)
    db_session.add_all(
        [
            Appointment(
                client_id=own_client.id,
                service_id=service.id,
                start_at=own_start,
                end_at=own_start + timedelta(minutes=60),
                status="scheduled",
                is_active=True,
            ),
            Appointment(
                client_id=other_client.id,
                service_id=service.id,
                start_at=other_start,
                end_at=other_start + timedelta(minutes=60),
                status="scheduled",
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/client/appointments", headers=headers)

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["service_id"] == service.id
    assert items[0]["service_name"] == service.name
    assert items[0]["start_at"] == own_start.isoformat()


def test_client_portal_requires_auth(client: TestClient, db_session: Session) -> None:
    """Client portal endpoints require authentication."""
    service = create_service(db_session, name="Service Client Auth Required", duration_minutes=60)
    monday = _next_weekday_date(0)

    availability_response = client.get(
        f"/api/v1/client/availability?service_id={service.id}&range=week&start_date={monday}"
    )
    appointments_response = client.get("/api/v1/client/appointments")

    assert availability_response.status_code == 401
    assert appointments_response.status_code == 401
