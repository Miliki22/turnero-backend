"""Client self-service booking routes."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_client_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.appointment import AppointmentOut
from app.schemas.client_portal import (
    ClientAppointmentCreate,
    ClientAppointmentListItemOut,
    ClientAvailabilitySlotOut,
    ClientServiceOut,
)
from app.services.client_portal_service import (
    create_client_appointment,
    list_active_services_for_client,
    list_client_appointments,
    list_client_availability,
    resolve_availability_range,
)

router = APIRouter(prefix="/client", tags=["client"])


@router.get("/services", response_model=list[ClientServiceOut])
def list_client_services_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_client_user),
) -> list[ClientServiceOut]:
    """List active services for authenticated clients."""
    return list_active_services_for_client(db=db)


@router.get("/availability", response_model=list[ClientAvailabilitySlotOut])
def list_client_availability_endpoint(
    service_id: int = Query(...),
    range: Literal["week", "fortnight"] = Query("week"),
    start_date: date | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_client_user),
) -> list[ClientAvailabilitySlotOut]:
    """List service availability for clients."""
    date_from, date_to = resolve_availability_range(range_name=range, start_date=start_date)
    return list_client_availability(
        db=db,
        service_id=service_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/appointments", response_model=list[ClientAppointmentListItemOut])
def list_client_appointments_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_client_user),
) -> list[ClientAppointmentListItemOut]:
    """List authenticated client appointments."""
    return list_client_appointments(
        db=db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.post("/appointments", response_model=AppointmentOut)
def create_client_appointment_endpoint(
    payload: ClientAppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_client_user),
) -> AppointmentOut:
    """Create a new appointment for authenticated client user."""
    return create_client_appointment(
        db=db,
        user_id=current_user.id,
        service_id=payload.service_id,
        start_at=payload.start_at,
    )
