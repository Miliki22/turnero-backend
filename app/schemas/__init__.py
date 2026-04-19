"""Schema package exports."""

from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    Token,
)
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate

__all__ = [
    "LoginRequest",
    "Token",
    "RegisterRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
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
