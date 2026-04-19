"""Client routes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_client_or_403, require_admin_user
from app.db.session import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.services.client_service import (
    create_client,
    delete_client,
    get_client,
    list_clients,
    update_client,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> ClientOut:
    """Create a new client (admin-only)."""
    return create_client(db=db, payload=payload)


@router.get("", response_model=list[ClientOut])
def list_clients_endpoint(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> list[ClientOut]:
    """List clients, active-only by default (admin-only)."""
    return list_clients(db=db, include_inactive=include_inactive)


@router.get("/me", response_model=ClientOut)
def get_my_client_endpoint(
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client_or_403),
) -> ClientOut:
    """Return authenticated client profile."""
    return get_client(db=db, client_id=current_client.id)


@router.get("/{client_id}", response_model=ClientOut)
def get_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> ClientOut:
    """Return one client by id (admin-only)."""
    return get_client(db=db, client_id=client_id)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client_endpoint(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> ClientOut:
    """Partially update a client (admin-only)."""
    return update_client(db=db, client_id=client_id, payload=payload)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_user),
) -> Response:
    """Soft-delete a client (admin-only)."""
    delete_client(db=db, client_id=client_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
