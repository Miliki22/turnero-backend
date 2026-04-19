"""Service routes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_client_user, require_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate
from app.services.service_service import (
    create_service,
    delete_service,
    get_service,
    list_services,
    update_service,
)

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service_endpoint(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> ServiceOut:
    """Create a new service (admin-only)."""
    return create_service(db=db, payload=payload)


@router.get("", response_model=list[ServiceOut])
def list_services_endpoint(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_client_user),
) -> list[ServiceOut]:
    """List services, active-only by default."""
    return list_services(db=db, include_inactive=include_inactive)


@router.get("/{service_id}", response_model=ServiceOut)
def get_service_endpoint(
    service_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_client_user),
) -> ServiceOut:
    """Return one service by id."""
    return get_service(db=db, service_id=service_id)


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service_endpoint(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> ServiceOut:
    """Partially update a service (admin-only)."""
    return update_service(db=db, service_id=service_id, payload=payload)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_endpoint(
    service_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> Response:
    """Soft-delete a service (admin-only)."""
    delete_service(db=db, service_id=service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
