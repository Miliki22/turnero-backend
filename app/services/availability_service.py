"""Business logic for availability slots."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.service import Service
from app.schemas.availability import AvailabilitySlotOut

BUSINESS_START = time(hour=9, minute=0)
BUSINESS_END = time(hour=19, minute=0)


def _get_active_service(db: Session, service_id: int) -> Service:
    """Return an active service or raise 404."""
    service = db.query(Service).filter(Service.id == service_id, Service.is_active.is_(True)).first()
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def list_availability_slots(
    db: Session,
    *,
    service_id: int,
    days_ahead: int = 14,
    include_past_days: int = 0,
    slot_minutes: int | None = None,
) -> list[AvailabilitySlotOut]:
    """Return availability slots marked as available/busy for a service and date window."""
    service = _get_active_service(db=db, service_id=service_id)
    slot_duration = timedelta(minutes=service.duration_minutes)
    slot_step = timedelta(minutes=slot_minutes if slot_minutes is not None else service.duration_minutes)
    tz = ZoneInfo(settings.tz)

    now = datetime.now(tz)
    window_start = now - timedelta(days=include_past_days)
    window_end = now + timedelta(days=days_ahead)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.is_active.is_(True),
            Appointment.status == "scheduled",
            Appointment.start_at < window_end,
            Appointment.end_at > window_start,
        )
        .all()
    )

    slots: list[AvailabilitySlotOut] = []
    current_day = window_start.date()
    last_day = window_end.date()

    while current_day <= last_day:
        day_start = datetime.combine(current_day, BUSINESS_START, tzinfo=tz)
        day_end = datetime.combine(current_day, BUSINESS_END, tzinfo=tz)
        if day_start.weekday() <= 4:
            slot_start = day_start
            while slot_start + slot_duration <= day_end:
                slot_end = slot_start + slot_duration
                if slot_end <= window_start or slot_start >= window_end:
                    slot_start += slot_step
                    continue

                is_busy = any(
                    slot_start < appointment.end_at and slot_end > appointment.start_at
                    for appointment in appointments
                )
                slots.append(
                    AvailabilitySlotOut(
                        start_at=slot_start,
                        end_at=slot_end,
                        status="busy" if is_busy else "available",
                    )
                )
                slot_start += slot_step
        current_day += timedelta(days=1)

    return slots
