from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.allocations.models import Allocation, AllocationStatus
from app.modules.assets.models import Asset
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.categories.models import AssetCategory
from app.modules.departments.models import Department
from app.modules.maintenance.models import MaintenanceRequest
from app.modules.reports.schemas import (
    AssetUsageCount,
    BookingHeatmapBucket,
    DepartmentUtilization,
    DueSoonAsset,
    MaintenanceFrequency,
    ReportsSummary,
)

RETIREMENT_AGE_YEARS = 5
DUE_SOON_WINDOW_DAYS = 30


class ReportsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def utilization_by_department(self) -> list[DepartmentUtilization]:
        statement = (
            select(
                Allocation.department_id,
                Department.name,
                func.count().label("count"),
            )
            .outerjoin(Department, Department.id == Allocation.department_id)
            .where(Allocation.status == AllocationStatus.ACTIVE)
            .group_by(Allocation.department_id, Department.name)
        )
        result = await self.session.execute(statement)
        return [
            DepartmentUtilization(department_id=dep_id, department_name=name, active_allocation_count=count)
            for dep_id, name, count in result.all()
        ]

    async def most_used_assets(self, limit: int = 5) -> list[AssetUsageCount]:
        statement = (
            select(Asset.id, Asset.tag, Asset.name, func.count(Booking.id).label("count"))
            .join(Booking, Booking.resource_id == Asset.id)
            .group_by(Asset.id, Asset.tag, Asset.name)
            .order_by(func.count(Booking.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [
            AssetUsageCount(asset_id=aid, asset_tag=tag, asset_name=name, usage_count=count)
            for aid, tag, name, count in result.all()
        ]

    async def idle_assets(self, limit: int = 5) -> list[AssetUsageCount]:
        statement = (
            select(Asset.id, Asset.tag, Asset.name, func.count(Booking.id).label("count"))
            .outerjoin(Booking, Booking.resource_id == Asset.id)
            .where(Asset.is_bookable.is_(True))
            .group_by(Asset.id, Asset.tag, Asset.name)
            .having(func.count(Booking.id) == 0)
            .order_by(Asset.created_at)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [
            AssetUsageCount(asset_id=aid, asset_tag=tag, asset_name=name, usage_count=count)
            for aid, tag, name, count in result.all()
        ]

    async def maintenance_frequency(self, limit: int = 10) -> list[MaintenanceFrequency]:
        statement = (
            select(
                Asset.id,
                Asset.tag,
                AssetCategory.name,
                func.count(MaintenanceRequest.id).label("count"),
            )
            .join(MaintenanceRequest, MaintenanceRequest.asset_id == Asset.id)
            .join(AssetCategory, AssetCategory.id == Asset.category_id)
            .group_by(Asset.id, Asset.tag, AssetCategory.name)
            .order_by(func.count(MaintenanceRequest.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return [
            MaintenanceFrequency(asset_id=aid, asset_tag=tag, category_name=cat, request_count=count)
            for aid, tag, cat, count in result.all()
        ]

    async def due_for_maintenance_or_retirement(self) -> list[DueSoonAsset]:
        today = date.today()
        due_soon_cutoff = today + timedelta(days=DUE_SOON_WINDOW_DAYS)
        retirement_cutoff = today - timedelta(days=365 * RETIREMENT_AGE_YEARS)

        due_soon_stmt = select(Asset).where(
            Asset.next_service_due_date.is_not(None),
            Asset.next_service_due_date <= due_soon_cutoff,
        )
        retiring_stmt = select(Asset).where(
            Asset.purchase_date.is_not(None),
            Asset.purchase_date <= retirement_cutoff,
        )

        due_soon = (await self.session.execute(due_soon_stmt)).scalars().all()
        retiring = (await self.session.execute(retiring_stmt)).scalars().all()

        results: list[DueSoonAsset] = []
        seen: set = set()
        for asset in due_soon:
            results.append(
                DueSoonAsset(
                    asset_id=asset.id,
                    asset_tag=asset.tag,
                    asset_name=asset.name,
                    next_service_due_date=asset.next_service_due_date,
                    purchase_date=asset.purchase_date,
                    reason="due for maintenance",
                )
            )
            seen.add(asset.id)
        for asset in retiring:
            if asset.id in seen:
                continue
            results.append(
                DueSoonAsset(
                    asset_id=asset.id,
                    asset_tag=asset.tag,
                    asset_name=asset.name,
                    next_service_due_date=asset.next_service_due_date,
                    purchase_date=asset.purchase_date,
                    reason="nearing retirement",
                )
            )
        return results

    async def booking_heatmap(self) -> list[BookingHeatmapBucket]:
        hour = func.hour(Booking.start_time)
        statement = (
            select(hour.label("hour_of_day"), func.count().label("count"))
            .where(Booking.status == BookingStatus.BOOKED)
            .group_by(hour)
            .order_by(hour)
        )
        result = await self.session.execute(statement)
        return [
            BookingHeatmapBucket(hour_of_day=int(hour_of_day), booking_count=count)
            for hour_of_day, count in result.all()
        ]

    async def summary(self) -> ReportsSummary:
        return ReportsSummary(
            utilization_by_department=await self.utilization_by_department(),
            most_used_assets=await self.most_used_assets(),
            idle_assets=await self.idle_assets(),
            maintenance_frequency=await self.maintenance_frequency(),
            due_for_maintenance_or_retirement=await self.due_for_maintenance_or_retirement(),
            booking_heatmap=await self.booking_heatmap(),
        )
