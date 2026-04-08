"""Schema package exports."""

from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.schemas.auth import LoginRequest, Token
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate

__all__ = [
    "LoginRequest",
    "Token",
    "ClientCreate",
    "ClientUpdate",
    "ClientOut",
    "ServiceCreate",
    "ServiceUpdate",
    "ServiceOut",
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentOut",
]
