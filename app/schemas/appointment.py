"""Schemas for appointment endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


AppointmentStatus = Literal["scheduled", "cancelled"]


class AppointmentCreate(BaseModel):
    """Request body used to create an appointment."""

    model_config = ConfigDict(str_strip_whitespace=True)

    client_id: int
    service_id: int
    start_at: datetime
    end_at: datetime | None = None
    notes: str | None = None
    status: AppointmentStatus = "scheduled"


class AppointmentUpdate(BaseModel):
    """Request body used to partially update an appointment."""

    model_config = ConfigDict(str_strip_whitespace=True)

    client_id: int | None = None
    service_id: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    notes: str | None = None
    status: AppointmentStatus | None = None
    is_active: bool | None = None


class AppointmentOut(BaseModel):
    """Response schema for appointment data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    service_id: int
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    notes: str | None
    is_active: bool
