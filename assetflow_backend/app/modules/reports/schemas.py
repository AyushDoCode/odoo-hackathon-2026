from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DepartmentUtilization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID | None
    department_name: str | None
    active_allocation_count: int


class AssetUsageCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    asset_tag: str
    asset_name: str
    usage_count: int


class MaintenanceFrequency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    asset_tag: str
    category_name: str
    request_count: int


class DueSoonAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    asset_tag: str
    asset_name: str
    next_service_due_date: date | None
    purchase_date: date | None
    reason: str


class BookingHeatmapBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hour_of_day: int
    booking_count: int


class ReportsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    utilization_by_department: list[DepartmentUtilization]
    most_used_assets: list[AssetUsageCount]
    idle_assets: list[AssetUsageCount]
    maintenance_frequency: list[MaintenanceFrequency]
    due_for_maintenance_or_retirement: list[DueSoonAsset]
    booking_heatmap: list[BookingHeatmapBucket]
