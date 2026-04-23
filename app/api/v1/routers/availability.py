"""Availability routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_client_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.availability import AvailabilitySlotOut
from app.services.availability_service import list_availability_slots

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=list[AvailabilitySlotOut])
def list_availability_endpoint(
    service_id: int = Query(...),
    days_ahead: int = Query(14, ge=1, le=30),
    include_past_days: int = Query(0, ge=0, le=7),
    slot_minutes: int | None = Query(None, ge=1, le=240),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_client_user),
) -> list[AvailabilitySlotOut]:
    """Return safe availability slots for client calendar booking."""
    return list_availability_slots(
        db=db,
        service_id=service_id,
        days_ahead=days_ahead,
        include_past_days=include_past_days,
        slot_minutes=slot_minutes,
    )
