"""Business logic for services."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate


def create_service(db: Session, payload: ServiceCreate) -> Service:
    """Create a service record."""
    service = Service(
        name=payload.name,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
        is_active=True,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def get_service(db: Session, service_id: int) -> Service:
    """Return a service by id or raise 404."""
    service = db.query(Service).filter(Service.id == service_id).first()
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def list_services(db: Session, include_inactive: bool = False) -> list[Service]:
    """List services, defaulting to active ones only."""
    query = db.query(Service)
    if not include_inactive:
        query = query.filter(Service.is_active.is_(True))
    return query.order_by(Service.id.asc()).all()


def update_service(db: Session, service_id: int, payload: ServiceUpdate) -> Service:
    """Update mutable service fields and return the persisted row."""
    service = get_service(db=db, service_id=service_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def delete_service(db: Session, service_id: int) -> None:
    """Soft-delete a service by setting is_active to false."""
    service = get_service(db=db, service_id=service_id)
    service.is_active = False
    db.add(service)
    db.commit()
