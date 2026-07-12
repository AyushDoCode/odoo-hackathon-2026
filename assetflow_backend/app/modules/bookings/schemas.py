from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.bookings.models import BookingStatus


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resource_id: UUID
    department_id: UUID | None = None
    start_time: datetime
    end_time: datetime
    purpose: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check_window(self) -> "BookingCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    resource_id: UUID
    user_id: UUID
    department_id: UUID | None
    start_time: datetime
    end_time: datetime
    purpose: str | None
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
