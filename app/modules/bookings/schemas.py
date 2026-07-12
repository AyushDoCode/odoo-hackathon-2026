from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.bookings.models import BookingStatus


class BookingViewStatus(StrEnum):
    UPCOMING = "UPCOMING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resource_id: UUID
    department_id: UUID | None = None
    start_time: datetime
    end_time: datetime
    purpose: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check_window(self) -> "BookingCreate":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.start_time <= datetime.now(UTC):
            raise ValueError("start_time must be in the future")
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
    status: BookingViewStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None

    @model_validator(mode="before")
    @classmethod
    def derive_status(cls, value):
        if isinstance(value, dict):
            data = dict(value)
        else:
            data = {
                name: getattr(value, name)
                for name in (
                    "id", "resource_id", "user_id", "department_id", "start_time",
                    "end_time", "purpose", "created_at", "updated_at", "created_by"
                )
            }
            data["status"] = getattr(value, "status")
        stored_status = data.get("status")
        if stored_status == BookingStatus.CANCELLED or stored_status == BookingStatus.CANCELLED.value:
            data["status"] = BookingViewStatus.CANCELLED
            return data
        now = datetime.now(UTC)
        start = data["start_time"]
        end = data["end_time"]
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if now < start:
            data["status"] = BookingViewStatus.UPCOMING
        elif now < end:
            data["status"] = BookingViewStatus.ONGOING
        else:
            data["status"] = BookingViewStatus.COMPLETED
        return data
