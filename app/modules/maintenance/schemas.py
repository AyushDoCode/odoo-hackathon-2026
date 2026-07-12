from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assets.schemas import AssetSummary
from app.modules.maintenance.models import MaintenancePriority, MaintenanceStatus
from app.modules.users.schemas import UserSummary


class MaintenanceRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: UUID
    issue: str = Field(min_length=1)
    priority: MaintenancePriority = Field(default=MaintenancePriority.MEDIUM)
    photo_url: str | None = Field(default=None, max_length=500)


class TechnicianAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technician_id: UUID


class MaintenanceRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    asset_id: UUID
    asset: AssetSummary
    issue: str
    priority: MaintenancePriority
    status: MaintenanceStatus
    technician_id: UUID | None
    technician: UserSummary | None
    approved_by: UUID | None
    photo_url: str | None
    opened_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
