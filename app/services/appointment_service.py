"""Business logic for appointments."""

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_at must be greater than start_at",
        )


def _ensure_no_overlap(
    db: Session,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: int | None = None,
) -> None:
    """Validate that there is no overlapping active scheduled appointment."""
    query = db.query(Appointment).filter(
        Appointment.is_active.is_(True),
        Appointment.status == "scheduled",
        Appointment.start_at < end_at,
        Appointment.end_at > start_at,
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
    _get_active_client(db=db, client_id=payload.client_id)
    service = _get_active_service(db=db, service_id=payload.service_id)

    end_at = payload.end_at or (payload.start_at + timedelta(minutes=service.duration_minutes))
    _validate_range(start_at=payload.start_at, end_at=end_at)

    if payload.status == "scheduled":
        _ensure_no_overlap(db=db, start_at=payload.start_at, end_at=end_at)

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
    return appointment


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

    _get_active_client(db=db, client_id=next_client_id)
    next_service = _get_active_service(db=db, service_id=next_service_id)

    if "end_at" in update_data:
        next_end_at = update_data["end_at"]
    elif "start_at" in update_data:
        next_end_at = next_start_at + timedelta(minutes=next_service.duration_minutes)
    else:
        next_end_at = appointment.end_at

    _validate_range(start_at=next_start_at, end_at=next_end_at)

    if next_is_active and next_status == "scheduled":
        _ensure_no_overlap(
            db=db,
            start_at=next_start_at,
            end_at=next_end_at,
            exclude_appointment_id=appointment.id,
        )

    for field, value in update_data.items():
        setattr(appointment, field, value)

    appointment.end_at = next_end_at
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def delete_appointment(db: Session, appointment_id: int) -> None:
    """Soft-delete an appointment by setting is_active to false."""
    appointment = get_appointment(db=db, appointment_id=appointment_id)
    appointment.is_active = False
    db.add(appointment)
    db.commit()
