from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import ActivityService
from app.modules.allocations.models import Allocation, AllocationStatus
from app.modules.allocations.repository import AllocationRepository
from app.modules.assets.models import AssetStatus
from app.modules.assets.repository import AssetRepository
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.bookings.repository import BookingRepository
from app.modules.maintenance.models import MaintenanceRequest
from app.modules.users.models import User, UserRole
from app.modules.activity.schemas import ActivityLogRead
from app.modules.dashboard.schemas import DashboardSummary


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assets = AssetRepository(session)
        self.allocations = AllocationRepository(session)
        self.bookings = BookingRepository(session)
        self.activity = ActivityService(session)

    async def summary(self, *, actor: User, upcoming_window_days: int = 7) -> DashboardSummary:
        # The dashboard is every role's first stop after login, so materializing
        # overdue/reminder notifications here (in addition to the notifications
        # endpoint) means they surface without a separate poll.
        await self.activity.sync_due_notifications(actor)

        now = datetime.now(UTC)
        today = now.date()

        assets_available = await self.assets.count_by_status(AssetStatus.AVAILABLE)
        manager = actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
        allocation_filters = []
        booking_filters = []
        maintenance_filters = []
        if not manager and actor.role == UserRole.DEPARTMENT_HEAD:
            allocation_filters.append(Allocation.department_id == actor.department_id)
            booking_filters.append(Booking.department_id == actor.department_id)
            # MaintenanceRequest carries no department of its own -- derive it from
            # any allocation (past or present) that ever put the asset in this
            # department, since maintenance approval already closes out the
            # allocation that was active when the request was raised.
            maintenance_filters.append(
                MaintenanceRequest.asset_id.in_(
                    select(Allocation.asset_id).where(
                        Allocation.department_id == actor.department_id
                    )
                )
            )
        elif not manager:
            allocation_filters.append(Allocation.to_user_id == actor.id)
            booking_filters.append(Booking.user_id == actor.id)
            maintenance_filters.append(MaintenanceRequest.created_by == actor.id)

        async def allocation_count(status_: AllocationStatus) -> int:
            statement = select(func.count()).select_from(Allocation).where(
                Allocation.status == status_, *allocation_filters
            )
            return int((await self.session.execute(statement)).scalar_one())

        allocated_statement = select(func.count()).select_from(Allocation).where(
            Allocation.status.in_(
                [
                    AllocationStatus.ACTIVE,
                    AllocationStatus.TRANSFER_REQUESTED,
                    AllocationStatus.RETURN_REQUESTED,
                ]
            ),
            *allocation_filters,
        )
        assets_allocated = int((await self.session.execute(allocated_statement)).scalar_one())
        day_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
        maintenance_statement = select(func.count()).select_from(MaintenanceRequest).where(
            MaintenanceRequest.opened_at >= day_start, *maintenance_filters
        )
        maintenance_today = int((await self.session.execute(maintenance_statement)).scalar_one())
        active_booking_statement = select(func.count()).select_from(Booking).where(
            Booking.status == BookingStatus.BOOKED,
            Booking.start_time <= now,
            Booking.end_time >= now,
            *booking_filters,
        )
        active_bookings = int((await self.session.execute(active_booking_statement)).scalar_one())
        pending_transfers = await allocation_count(AllocationStatus.TRANSFER_REQUESTED)
        overdue_statement = select(Allocation).where(
            Allocation.status.in_([AllocationStatus.ACTIVE, AllocationStatus.RETURN_REQUESTED]),
            Allocation.expected_return_date.is_not(None),
            Allocation.expected_return_date < today,
            *allocation_filters,
        )
        overdue = list((await self.session.execute(overdue_statement)).scalars().all())
        from datetime import timedelta
        upcoming_statement = select(Allocation).where(
            Allocation.status == AllocationStatus.ACTIVE,
            Allocation.expected_return_date.is_not(None),
            Allocation.expected_return_date >= today,
            Allocation.expected_return_date <= today + timedelta(days=upcoming_window_days),
            *allocation_filters,
        )
        upcoming = list((await self.session.execute(upcoming_statement)).scalars().all())
        recent_activity = await self.activity.feed(
            recipient_id=None if manager else actor.id,
            audit_log_only=manager,
            limit=10,
        )

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
