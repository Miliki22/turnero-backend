"""Appointment routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_current_client_or_403, require_admin_user
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.services.appointment_service import (
    create_appointment,
    delete_appointment,
    get_appointment,
    list_appointments,
    send_client_created_appointment_notification,
    update_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment_endpoint(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AppointmentOut:
    """Create a new appointment."""
    create_payload = payload
    if current_user.role == "client":
        client = db.query(Client).filter(Client.user_id == current_user.id, Client.is_active.is_(True)).first()
        if client is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client profile not found")
        create_payload = payload.model_copy(update={"client_id": client.id})
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    appointment = create_appointment(db=db, payload=create_payload)
    if current_user.role == "client":
        send_client_created_appointment_notification(db=db, appointment=appointment)
    return appointment


@router.get("", response_model=list[AppointmentOut])
def list_appointments_endpoint(
    client_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[AppointmentOut]:
    """List appointments with optional filters."""
    target_client_id = client_id
    if current_user.role == "client":
        client = db.query(Client).filter(Client.user_id == current_user.id, Client.is_active.is_(True)).first()
        if client is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client profile not found")
        target_client_id = client.id
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    return list_appointments(
        db=db,
        client_id=target_client_id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get("/me", response_model=list[AppointmentOut])
def list_my_appointments_endpoint(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    client: Client = Depends(get_current_client_or_403),
) -> list[AppointmentOut]:
    """List appointments for authenticated client profile."""
    return list_appointments(
        db=db,
        client_id=client.id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AppointmentOut:
    """Return one appointment by id."""
    appointment = get_appointment(db=db, appointment_id=appointment_id)
    if current_user.role == "client":
        client = db.query(Client).filter(Client.user_id == current_user.id, Client.is_active.is_(True)).first()
        if client is None or appointment.client_id != client.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> AppointmentOut:
    """Partially update an appointment (admin-only)."""
    return update_appointment(db=db, appointment_id=appointment_id, payload=payload)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> Response:
    """Soft-delete an appointment (admin-only)."""
    delete_appointment(db=db, appointment_id=appointment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
