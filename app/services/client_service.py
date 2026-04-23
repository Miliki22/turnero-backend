"""Business logic for clients."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate
from app.services.auth_service import get_password_hash


def create_client(db: Session, payload: ClientCreate) -> Client:
    """Create a client record."""
    email = (payload.email or "").strip().lower()
    if not email:
        email = f"client-{uuid4().hex[:20]}@local.invalid"

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            password_hash=get_password_hash(uuid4().hex),
            role="client",
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        existing_client = db.query(Client).filter(Client.user_id == user.id).first()
        if existing_client is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    client = Client(
        user_id=user.id,
        full_name=payload.full_name,
        phone=payload.phone,
        email=email if payload.email else None,
        notes=payload.notes,
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def get_client(db: Session, client_id: int) -> Client:
    """Return a client by id or raise 404."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def list_clients(db: Session, include_inactive: bool = False) -> list[Client]:
    """List clients, defaulting to active ones only."""
    query = db.query(Client)
    if not include_inactive:
        query = query.filter(Client.is_active.is_(True))
    return query.order_by(Client.id.asc()).all()


def update_client(db: Session, client_id: int, payload: ClientUpdate) -> Client:
    """Update mutable client fields and return the persisted row."""
    client = get_client(db=db, client_id=client_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"] is not None:
        next_email = update_data["email"].strip().lower()
        duplicate = db.query(User).filter(User.email == next_email, User.id != client.user_id).first()
        if duplicate is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        user = db.query(User).filter(User.id == client.user_id).first()
        if user is not None:
            user.email = next_email
            db.add(user)

    for field, value in update_data.items():
        setattr(client, field, value)

    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client_id: int) -> None:
    """Soft-delete a client by setting is_active to false."""
    client = get_client(db=db, client_id=client_id)
    client.is_active = False
    db.add(client)
    db.commit()


def get_client_dashboard(db: Session, client_id: int, recent_limit: int = 10) -> dict[str, object]:
    """Return dashboard data for one client."""
    client = get_client(db=db, client_id=client_id)
    now = datetime.now(timezone.utc)

    next_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.client_id == client.id,
            Appointment.is_active.is_(True),
            Appointment.status == "scheduled",
            Appointment.start_at >= now,
        )
        .order_by(Appointment.start_at.asc(), Appointment.id.asc())
        .first()
    )

    recent_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.client_id == client.id,
            Appointment.is_active.is_(True),
        )
        .order_by(Appointment.start_at.desc(), Appointment.id.desc())
        .limit(recent_limit)
        .all()
    )

    active_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.client_id == client.id,
            Appointment.is_active.is_(True),
        )
        .all()
    )
    total_appointments = len(active_appointments)
    last_appointment_at = max((item.start_at for item in active_appointments), default=None)

    return {
        "client": client,
        "next_appointment": next_appointment,
        "recent_appointments": recent_appointments,
        "stats": {
            "total_appointments": total_appointments,
            "last_appointment_at": last_appointment_at,
        },
    }
