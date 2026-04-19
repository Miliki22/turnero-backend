"""Business logic for appointments."""

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.email_service import send_appointment_confirmation_email
from app.services.google_calendar_service import (
    get_connected_admin_integration,
    get_google_calendar_client,
)

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
BUFFER_MINUTES = 15
ALLOWED_DURATIONS_MINUTES = {60, 90, 120}
BUSINESS_START = time(hour=9, minute=0)
BUSINESS_END = time(hour=19, minute=0)
logger = logging.getLogger(__name__)


def _get_active_client(db: Session, client_id: int) -> Client:
    """Return an active client or raise 404."""
    client = db.query(Client).filter(Client.id == client_id, Client.is_active.is_(True)).first()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def _get_active_service(db: Session, service_id: int) -> Service:
    """Return an active service or raise 404."""
    service = db.query(Service).filter(Service.id == service_id, Service.is_active.is_(True)).first()
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def _validate_range(start_at: datetime, end_at: datetime) -> None:
    """Validate appointment range ordering."""
    if end_at <= start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_at must be greater than start_at",
        )


def _normalize_to_ar(dt: datetime) -> datetime:
    """Normalize a datetime to Argentina timezone for rule validations."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=AR_TZ)
    return dt.astimezone(AR_TZ)


def _validate_duration(start_at_ar: datetime, end_at_ar: datetime) -> None:
    """Validate appointment duration against allowed values."""
    duration_minutes = int((end_at_ar - start_at_ar).total_seconds() // 60)
    if duration_minutes not in ALLOWED_DURATIONS_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Duration must be one of: 60, 90, 120 minutes",
        )


def _validate_schedule_window(start_at_ar: datetime, end_at_ar: datetime, override_schedule: bool) -> None:
    """Validate weekdays and business hours when schedule override is disabled."""
    if override_schedule:
        return

    if start_at_ar.weekday() > 4 or end_at_ar.weekday() > 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Appointments are only allowed Monday to Friday",
        )

    if start_at_ar.time() < BUSINESS_START or end_at_ar.time() > BUSINESS_END:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Appointment must be within business hours (09:00-19:00)",
        )


def _ensure_no_overlap(
    db: Session,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: int | None = None,
) -> None:
    """Validate that there is no overlapping active scheduled appointment."""
    buffer_delta = timedelta(minutes=BUFFER_MINUTES)
    query = db.query(Appointment).filter(
        Appointment.is_active.is_(True),
        Appointment.status == "scheduled",
        Appointment.start_at < end_at + buffer_delta,
        Appointment.end_at > start_at - buffer_delta,
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)

    overlapping = query.first()
    if overlapping is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment overlaps with an existing scheduled appointment",
        )


def create_appointment(db: Session, payload: AppointmentCreate) -> Appointment:
    """Create an appointment with overlap and entity validations.

    If end_at is omitted, it is calculated using service.duration_minutes.
    """
    if payload.client_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="client_id is required",
        )

    _get_active_client(db=db, client_id=payload.client_id)
    service = _get_active_service(db=db, service_id=payload.service_id)

    end_at = payload.end_at or (payload.start_at + timedelta(minutes=service.duration_minutes))
    _validate_range(start_at=payload.start_at, end_at=end_at)
    start_at_ar = _normalize_to_ar(payload.start_at)
    end_at_ar = _normalize_to_ar(end_at)
    _validate_duration(start_at_ar=start_at_ar, end_at_ar=end_at_ar)
    _validate_schedule_window(
        start_at_ar=start_at_ar,
        end_at_ar=end_at_ar,
        override_schedule=payload.override_schedule,
    )

    if payload.status == "scheduled":
        _ensure_no_overlap(db=db, start_at=start_at_ar, end_at=end_at_ar)

    appointment = Appointment(
        client_id=payload.client_id,
        service_id=payload.service_id,
        start_at=payload.start_at,
        end_at=end_at,
        status=payload.status,
        notes=payload.notes,
        is_active=True,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    _sync_google_create_event(db=db, appointment=appointment)
    return appointment


def send_client_created_appointment_notification(db: Session, appointment: Appointment) -> None:
    """Send appointment confirmation emails after client self-booking."""
    client = db.query(Client).filter(Client.id == appointment.client_id).first()
    service = db.query(Service).filter(Service.id == appointment.service_id).first()
    if client is None or service is None:
        return

    client_email = client.email
    if not client_email:
        user = db.query(User).filter(User.id == client.user_id).first()
        client_email = user.email if user is not None else ""
    if not client_email:
        return

    try:
        send_appointment_confirmation_email(
            client_email=client_email,
            admin_email=settings.admin_notify_email,
            client_name=client.full_name,
            service_name=service.name,
            start_at=appointment.start_at,
            end_at=appointment.end_at,
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to send appointment confirmation email")


def _build_google_event_payload(db: Session, appointment: Appointment) -> dict[str, object]:
    """Build Google Calendar event payload from appointment data."""
    client = db.query(Client).filter(Client.id == appointment.client_id).first()
    service = db.query(Service).filter(Service.id == appointment.service_id).first()
    client_name = client.full_name if client is not None else "Cliente"
    service_name = service.name if service is not None else "Turno"
    return {
        "summary": f"{service_name} - {client_name}",
        "description": f"Cliente: {client_name}\nServicio: {service_name}",
        "start": {"dateTime": appointment.start_at.isoformat()},
        "end": {"dateTime": appointment.end_at.isoformat()},
    }


def _sync_google_create_event(db: Session, appointment: Appointment) -> None:
    """Create Google Calendar event when integration is enabled and connected."""
    if not settings.google_sync_enabled:
        return

    integration = get_connected_admin_integration(db=db)
    if integration is None:
        logger.warning("Google sync enabled but admin integration is not connected")
        return

    try:
        client = get_google_calendar_client(db=db, integration=integration)
        event_id = client.create_event(_build_google_event_payload(db=db, appointment=appointment))
        appointment.google_event_id = event_id
        db.add(appointment)
        db.commit()
    except Exception:
        logger.warning("Failed to create Google Calendar event for appointment id=%s", appointment.id, exc_info=True)


def _sync_google_update_event(db: Session, appointment: Appointment) -> None:
    """Update linked Google Calendar event if sync is enabled and event exists."""
    if not settings.google_sync_enabled:
        return
    if not appointment.google_event_id:
        return

    integration = get_connected_admin_integration(db=db)
    if integration is None:
        logger.warning("Google sync enabled but admin integration is not connected")
        return

    try:
        client = get_google_calendar_client(db=db, integration=integration)
        client.update_event(
            google_event_id=appointment.google_event_id,
            event_payload=_build_google_event_payload(db=db, appointment=appointment),
        )
    except Exception:
        logger.warning("Failed to update Google Calendar event for appointment id=%s", appointment.id, exc_info=True)


def _sync_google_delete_event(db: Session, appointment: Appointment) -> None:
    """Delete linked Google Calendar event when appointment is deleted."""
    if not settings.google_sync_enabled:
        return
    if not appointment.google_event_id:
        return

    integration = get_connected_admin_integration(db=db)
    if integration is None:
        logger.warning("Google sync enabled but admin integration is not connected")
        return

    try:
        client = get_google_calendar_client(db=db, integration=integration)
        client.delete_event(google_event_id=appointment.google_event_id)
    except Exception:
        logger.warning("Failed to delete Google Calendar event for appointment id=%s", appointment.id, exc_info=True)


def get_appointment(db: Session, appointment_id: int) -> Appointment:
    """Return an appointment by id or raise 404."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return appointment


def list_appointments(
    db: Session,
    client_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_inactive: bool = False,
) -> list[Appointment]:
    """List appointments with optional filters."""
    query = db.query(Appointment)
    if not include_inactive:
        query = query.filter(Appointment.is_active.is_(True))
    if client_id is not None:
        query = query.filter(Appointment.client_id == client_id)
    if date_from is not None:
        query = query.filter(Appointment.start_at >= date_from)
    if date_to is not None:
        query = query.filter(Appointment.start_at <= date_to)

    return query.order_by(Appointment.start_at.asc(), Appointment.id.asc()).all()


def update_appointment(
    db: Session,
    appointment_id: int,
    payload: AppointmentUpdate,
) -> Appointment:
    """Update mutable appointment fields with full validation."""
    appointment = get_appointment(db=db, appointment_id=appointment_id)
    update_data = payload.model_dump(exclude_unset=True)

    next_client_id = update_data.get("client_id", appointment.client_id)
    next_service_id = update_data.get("service_id", appointment.service_id)
    next_start_at = update_data.get("start_at", appointment.start_at)
    next_status = update_data.get("status", appointment.status)
    next_is_active = update_data.get("is_active", appointment.is_active)
    payload_override_schedule = update_data.pop("override_schedule", None)
    current_override_schedule = getattr(appointment, "override_schedule", False)
    next_override_schedule = current_override_schedule if payload_override_schedule is None else payload_override_schedule

    _get_active_client(db=db, client_id=next_client_id)
    next_service = _get_active_service(db=db, service_id=next_service_id)

    if "end_at" in update_data:
        next_end_at = update_data["end_at"]
    elif "start_at" in update_data:
        next_end_at = next_start_at + timedelta(minutes=next_service.duration_minutes)
    else:
        next_end_at = appointment.end_at

    _validate_range(start_at=next_start_at, end_at=next_end_at)
    next_start_at_ar = _normalize_to_ar(next_start_at)
    next_end_at_ar = _normalize_to_ar(next_end_at)
    _validate_duration(start_at_ar=next_start_at_ar, end_at_ar=next_end_at_ar)
    _validate_schedule_window(
        start_at_ar=next_start_at_ar,
        end_at_ar=next_end_at_ar,
        override_schedule=next_override_schedule,
    )

    if next_is_active and next_status == "scheduled":
        _ensure_no_overlap(
            db=db,
            start_at=next_start_at_ar,
            end_at=next_end_at_ar,
            exclude_appointment_id=appointment.id,
        )

    for field, value in update_data.items():
        setattr(appointment, field, value)

    appointment.end_at = next_end_at
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    _sync_google_update_event(db=db, appointment=appointment)
    return appointment


def delete_appointment(db: Session, appointment_id: int) -> None:
    """Soft-delete an appointment by setting is_active to false."""
    appointment = get_appointment(db=db, appointment_id=appointment_id)
    _sync_google_delete_event(db=db, appointment=appointment)
    appointment.is_active = False
    db.add(appointment)
    db.commit()
