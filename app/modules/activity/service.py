from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.models import ActivityLog
from app.modules.activity.repository import ActivityRepository
from app.modules.allocations.models import Allocation, AllocationStatus
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.users.models import User


async def record(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action_type: str,
    category: str,
    target_type: str,
    target_id: UUID | None,
    message: str,
    recipient_id: UUID | None = None,
) -> ActivityLog:
    """The single funnel every other service calls to write an activity/notification
    entry. Uses flush (not commit) so it rides along in the caller's own transaction --
    the caller's commit is what actually persists it.
    """
    log = ActivityLog(
        actor_id=actor_id,
        recipient_id=recipient_id,
        action_type=action_type,
        category=category,
        target_type=target_type,
        target_id=target_id,
        message=message,
    )
    ActivityRepository(session).add(log)
    await session.flush()
    return log


async def notify(
    session: AsyncSession,
    *,
    recipient_id: UUID,
    action_type: str,
    category: str,
    target_type: str,
    target_id: UUID | None,
    message: str,
    actor_id: UUID | None = None,
) -> ActivityLog:
    return await record(
        session,
        actor_id=actor_id,
        recipient_id=recipient_id,
        action_type=action_type,
        category=category,
        target_type=target_type,
        target_id=target_id,
        message=message,
    )


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ActivityRepository(session)

    async def feed(
        self,
        *,
        category: str | None = None,
        recipient_id: UUID | None = None,
        audit_log_only: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ActivityLog]:
        return await self.repository.feed(
            category=category,
            recipient_id=recipient_id,
            audit_log_only=audit_log_only,
            offset=offset,
            limit=limit,
        )

    async def sync_due_notifications(self, user: User) -> None:
        now = datetime.now(UTC)
        today = now.date()
        overdue_statement = select(Allocation).where(
            Allocation.to_user_id == user.id,
            Allocation.status.in_([AllocationStatus.ACTIVE, AllocationStatus.RETURN_REQUESTED]),
            Allocation.expected_return_date.is_not(None),
            Allocation.expected_return_date < today,
        )
        overdue = list((await self.session.execute(overdue_statement)).scalars().all())
        reminder_cutoff = now + timedelta(hours=1)
        booking_statement = select(Booking).where(
            Booking.user_id == user.id,
            Booking.status == BookingStatus.BOOKED,
            Booking.start_time > now,
            Booking.start_time <= reminder_cutoff,
        )
        upcoming = list((await self.session.execute(booking_statement)).scalars().all())

        for allocation in overdue:
            if not await self.repository.notification_exists(
                recipient_id=user.id,
                action_type="allocation.overdue",
                target_id=allocation.id,
            ):
                await notify(
                    self.session,
                    recipient_id=user.id,
                    action_type="allocation.overdue",
                    category="alerts",
                    target_type="allocation",
                    target_id=allocation.id,
                    message=f"Asset {allocation.asset_id} is overdue for return",
                )
        for booking in upcoming:
            if not await self.repository.notification_exists(
                recipient_id=user.id,
                action_type="booking.reminder",
                target_id=booking.id,
            ):
                await notify(
                    self.session,
                    recipient_id=user.id,
                    action_type="booking.reminder",
                    category="bookings",
                    target_type="booking",
                    target_id=booking.id,
                    message=f"Booking for resource {booking.resource_id} starts within one hour",
                )
        await self.session.commit()

    async def mark_read(self, log_id: UUID, *, recipient_id: UUID) -> ActivityLog | None:
        log = await self.repository.get_for_recipient(log_id, recipient_id)
        if log is None:
            return None
        log.is_read = True
        await self.session.commit()
        await self.session.refresh(log)
        return log
