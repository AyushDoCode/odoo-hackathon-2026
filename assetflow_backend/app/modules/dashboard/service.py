from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import ActivityService
from app.modules.allocations.models import AllocationStatus
from app.modules.allocations.repository import AllocationRepository
from app.modules.assets.models import AssetStatus
from app.modules.assets.repository import AssetRepository
from app.modules.bookings.repository import BookingRepository
from app.modules.activity.schemas import ActivityLogRead
from app.modules.dashboard.schemas import DashboardSummary


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = AssetRepository(session)
        self.allocations = AllocationRepository(session)
        self.bookings = BookingRepository(session)
        self.activity = ActivityService(session)

    async def summary(self, *, upcoming_window_days: int = 7) -> DashboardSummary:
        now = datetime.now(UTC)
        today = date.today()

        assets_available = await self.assets.count_by_status(AssetStatus.AVAILABLE)
        assets_allocated = await self.assets.count_by_status(AssetStatus.ALLOCATED)
        maintenance_today = await self.assets.count_by_status(AssetStatus.MAINTENANCE)
        active_bookings = await self.bookings.count_ongoing(as_of=now)
        pending_transfers = await self.allocations.count_by_status(
            AllocationStatus.TRANSFER_REQUESTED
        )
        overdue = await self.allocations.overdue(as_of=today)
        upcoming = await self.allocations.upcoming_returns(
            as_of=today, within_days=upcoming_window_days
        )
        recent_activity = await self.activity.feed(limit=10)

        return DashboardSummary(
            assets_available=assets_available,
            assets_allocated=assets_allocated,
            maintenance_today=maintenance_today,
            active_bookings=active_bookings,
            pending_transfers=pending_transfers,
            upcoming_returns=len(upcoming),
            overdue_returns=len(overdue),
            recent_activity=[ActivityLogRead.model_validate(a) for a in recent_activity],
        )
