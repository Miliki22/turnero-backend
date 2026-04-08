"""Client routes (admin-only)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
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
    _: User = Depends(get_current_user),
) -> ClientOut:
    """Create a new client."""
    return create_client(db=db, payload=payload)


@router.get("", response_model=list[ClientOut])
def list_clients_endpoint(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ClientOut]:
    """List clients, active-only by default."""
    return list_clients(db=db, include_inactive=include_inactive)


@router.get("/{client_id}", response_model=ClientOut)
def get_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ClientOut:
    """Return one client by id."""
    return get_client(db=db, client_id=client_id)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client_endpoint(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ClientOut:
    """Partially update a client."""
    return update_client(db=db, client_id=client_id, payload=payload)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Soft-delete a client."""
    delete_client(db=db, client_id=client_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
