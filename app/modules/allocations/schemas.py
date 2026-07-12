from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.allocations.models import AllocationStatus


class AllocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: UUID
    to_user_id: UUID | None = None
    department_id: UUID | None = None
    reason: str | None = None
    expected_return_date: date | None = None


class TransferRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    to_user_id: UUID
    reason: str | None = None


class ReturnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    return_condition: str = Field(min_length=1, max_length=255)


class AllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    asset_id: UUID
    from_user_id: UUID | None
    to_user_id: UUID | None
    department_id: UUID | None
    reason: str | None
    status: AllocationStatus
    allocated_at: datetime
    returned_at: datetime | None
    return_condition: str | None
    expected_return_date: date | None
    transfer_to_user_id: UUID | None
    approved_by: UUID | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
