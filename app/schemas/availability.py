"""Schemas for availability endpoint."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


AvailabilityStatus = Literal["available", "busy"]


class AvailabilitySlotOut(BaseModel):
    """Represents one availability slot status."""

    model_config = ConfigDict(from_attributes=True)

    start_at: datetime
    end_at: datetime
    status: AvailabilityStatus
