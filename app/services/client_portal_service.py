"""Business logic for client self-service booking flow."""

from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.schemas.appointment import AppointmentCreate
from app.schemas.client_portal import ClientAvailabilitySlotOut, ClientAppointmentListItemOut
from app.services.appointment_service import create_appointment

BUSINESS_START = time(hour=9, minute=0)
BUSINESS_END = time(hour=19, minute=0)


def _get_active_service(db: Session, service_id: int) -> Service:
    """Return active service or raise 404."""
    service = db.query(Service).filter(Service.id == service_id, Service.is_active.is_(True)).first()
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def _get_client_profile_or_400(db: Session, user_id: int) -> Client:
    """Return active client profile linked to user or raise 400."""
    client = db.query(Client).filter(Client.user_id == user_id, Client.is_active.is_(True)).first()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client profile not found for user",
        )
    return client


def _normalize_to_local(dt: datetime) -> datetime:
    """Normalize datetime to application timezone."""
    tz = ZoneInfo(settings.tz)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def list_active_services_for_client(db: Session) -> list[Service]:
    """Return active services for client booking."""
    return (
        db.query(Service)
        .filter(Service.is_active.is_(True))
        .order_by(Service.name.asc(), Service.id.asc())
        .all()
    )


def list_client_availability(
    db: Session,
    *,
    service_id: int,
    date_from: date,
    date_to: date,
) -> list[ClientAvailabilitySlotOut]:
    """List availability slots for a service in a date range.

    `date_to` is treated as inclusive.
    """
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be greater than or equal to date_from",
        )

    service = _get_active_service(db=db, service_id=service_id)
    tz = ZoneInfo(settings.tz)
    slot_duration = timedelta(minutes=service.duration_minutes)

    window_start = datetime.combine(date_from, time.min, tzinfo=tz)
    window_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
    scheduled = (
        db.query(Appointment)
        .filter(
            Appointment.is_active.is_(True),
            Appointment.status == "scheduled",
            Appointment.start_at < window_end,
            Appointment.end_at > window_start,
        )
        .all()
    )

    slots: list[ClientAvailabilitySlotOut] = []
    current_day = date_from
    while current_day <= date_to:
        if current_day.weekday() <= 4:
            day_start = datetime.combine(current_day, BUSINESS_START, tzinfo=tz)
            day_end = datetime.combine(current_day, BUSINESS_END, tzinfo=tz)
            slot_start = day_start
            while slot_start + slot_duration <= day_end:
                slot_end = slot_start + slot_duration
                occupied = any(
                    slot_start < item.end_at and slot_end > item.start_at
                    for item in scheduled
                )
                slots.append(
                    ClientAvailabilitySlotOut(
                        start_at=slot_start,
                        end_at=slot_end,
                        status="occupied" if occupied else "available",
                    )
                )
                slot_start += slot_duration
        current_day += timedelta(days=1)

    return slots


def list_client_appointments(
    db: Session,
    *,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[ClientAppointmentListItemOut]:
    """List authenticated client appointments (history + upcoming)."""
    client = _get_client_profile_or_400(db=db, user_id=user_id)
    rows = (
        db.query(Appointment, Service)
        .join(Service, Service.id == Appointment.service_id)
        .filter(
            Appointment.client_id == client.id,
            Appointment.is_active.is_(True),
        )
        .order_by(Appointment.start_at.desc(), Appointment.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        ClientAppointmentListItemOut(
            id=appointment.id,
            service_id=appointment.service_id,
            service_name=service.name,
            start_at=appointment.start_at,
            end_at=appointment.end_at,
            status=appointment.status,
        )
        for appointment, service in rows
    ]


def resolve_availability_range(
    *,
    range_name: Literal["week", "fortnight"] = "week",
    start_date: date | None = None,
) -> tuple[date, date]:
    """Resolve date_from/date_to (inclusive) from range parameters."""
    start = start_date or datetime.now(ZoneInfo(settings.tz)).date()
    days = 7 if range_name == "week" else 14
    end = start + timedelta(days=days - 1)
    return start, end


def create_client_appointment(
    db: Session,
    *,
    user_id: int,
    service_id: int,
    start_at: datetime,
) -> Appointment:
    """Create appointment for authenticated client."""
    client = _get_client_profile_or_400(db=db, user_id=user_id)
    service = _get_active_service(db=db, service_id=service_id)

    local_start = _normalize_to_local(start_at)
    local_end = local_start + timedelta(minutes=service.duration_minutes)
    if local_start.weekday() > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointments are only allowed Monday to Friday",
        )
    if local_start.time() < BUSINESS_START or local_end.time() > BUSINESS_END:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment must be within business hours (09:00-19:00)",
        )

    payload = AppointmentCreate(
        client_id=client.id,
        service_id=service.id,
        start_at=start_at,
    )
    return create_appointment(db=db, payload=payload)
