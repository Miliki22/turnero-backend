"""Business logic for clients."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


def create_client(db: Session, payload: ClientCreate) -> Client:
    """Create a client record."""
    client = Client(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
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
