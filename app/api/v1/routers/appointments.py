"""Appointment routes (admin-only)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.services.appointment_service import (
    create_appointment,
    delete_appointment,
    get_appointment,
    list_appointments,
    update_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment_endpoint(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AppointmentOut:
    """Create a new appointment."""
    return create_appointment(db=db, payload=payload)


@router.get("", response_model=list[AppointmentOut])
def list_appointments_endpoint(
    client_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AppointmentOut]:
    """List appointments with optional filters."""
    return list_appointments(
        db=db,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AppointmentOut:
    """Return one appointment by id."""
    return get_appointment(db=db, appointment_id=appointment_id)


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AppointmentOut:
    """Partially update an appointment."""
    return update_appointment(db=db, appointment_id=appointment_id, payload=payload)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Soft-delete an appointment."""
    delete_appointment(db=db, appointment_id=appointment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
