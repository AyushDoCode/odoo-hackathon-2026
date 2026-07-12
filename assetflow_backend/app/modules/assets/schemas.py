from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assets.models import AssetStatus
from app.modules.categories.schemas import AssetCategoryRead


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    category_id: UUID
    location: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=255)
    qr_code: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    notes: str | None = None
    acquisition_cost: float | None = Field(default=None, ge=0)
    condition: str | None = Field(default=None, max_length=100)
    photo_url: str | None = Field(default=None, max_length=500)
    is_bookable: bool = Field(default=False)
    next_service_due_date: date | None = None


class AssetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=255)
    qr_code: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    notes: str | None = None
    acquisition_cost: float | None = Field(default=None, ge=0)
    condition: str | None = Field(default=None, max_length=100)
    photo_url: str | None = Field(default=None, max_length=500)
    is_bookable: bool | None = None
    next_service_due_date: date | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    tag: str
    name: str
    category_id: UUID
    category: AssetCategoryRead
    status: AssetStatus
    location: str | None
    serial_number: str | None
    qr_code: str | None
    purchase_date: date | None
    notes: str | None
    acquisition_cost: float | None
    condition: str | None
    photo_url: str | None
    is_bookable: bool
    next_service_due_date: date | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
