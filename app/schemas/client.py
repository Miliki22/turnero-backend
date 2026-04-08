"""Schemas for client endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class ClientCreate(BaseModel):
    """Request body used to create a client."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class ClientUpdate(BaseModel):
    """Request body used to partially update a client."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    is_active: bool | None = None


class ClientOut(BaseModel):
    """Response schema for client data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str
    email: str | None
    notes: str | None
    is_active: bool
