"""Schemas for client self-service endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClientServiceOut(BaseModel):
    """Public service fields for client booking flow."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    duration_minutes: int
    price: Decimal | None


class ClientAvailabilitySlotOut(BaseModel):
    """One slot with safe availability status."""

    start_at: datetime
    end_at: datetime
    status: Literal["available", "occupied"]


class ClientAppointmentCreate(BaseModel):
    """Request body for client appointment creation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    service_id: int
    start_at: datetime


class ClientAppointmentListItemOut(BaseModel):
    """List item for authenticated client appointments."""

    id: int
    service_id: int
    service_name: str
    start_at: datetime
    end_at: datetime
    status: str
