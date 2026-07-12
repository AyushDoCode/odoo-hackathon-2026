from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.audit.models import AuditCycleStatus, VerificationResult


class AuditCycleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    department_id: UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    start_date: date
    end_date: date
    auditor_ids: list[UUID] = Field(min_length=1)
    asset_ids: list[UUID] = Field(min_length=1, description="Assets in scope for this cycle")

    @model_validator(mode="after")
    def _check_dates(self) -> "AuditCycleCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date")
        return self


class AuditItemVerify(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    verification: VerificationResult
    notes: str | None = None


class AuditItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    cycle_id: UUID
    asset_id: UUID
    expected_location: str | None
    verification: VerificationResult | None
    notes: str | None


class AuditCycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    department_id: UUID | None
    location: str | None
    start_date: date
    end_date: date
    auditor_ids: list[str]
    status: AuditCycleStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None


class AuditCycleDetail(AuditCycleRead):
    items: list[AuditItemRead]


class DiscrepancyReport(BaseModel):
    cycle_id: UUID
    missing: list[AuditItemRead]
    damaged: list[AuditItemRead]
