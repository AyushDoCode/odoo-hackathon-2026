from __future__ import annotations

from uuid import UUID
from typing import Any
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class AssetCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    description: str | None
    custom_fields: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssetCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    custom_fields: dict[str, Any] | None = None
    is_active: bool | None = None
