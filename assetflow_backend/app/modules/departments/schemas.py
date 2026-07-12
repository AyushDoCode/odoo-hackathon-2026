from __future__ import annotations

from uuid import UUID
from datetime import datetimert UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    parent_department_id: UUID | None = None
    head_id: UUID | None = None
    is_active: bool = Field(default=True)


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    description: str | None
    parent_department_id: UUID | None
    head_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    parent_department_id: UUID | None = None
    head_id: UUID | None = None
    is_active: bool | None = None
