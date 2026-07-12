from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.models import ActivityLog
from app.modules.activity.repository import ActivityRepository


async def record(
    session: AsyncSession,
    *,
    actor_id: UUID | None,
    action_type: str,
    category: str,
    target_type: str,
    target_id: UUID | None,
    message: str,
) -> ActivityLog:
    """The single funnel every other service calls to write an activity/notification
    entry. Uses flush (not commit) so it rides along in the caller's own transaction --
    the caller's commit is what actually persists it.
    """
    log = ActivityLog(
        actor_id=actor_id,
        action_type=action_type,
        category=category,
        target_type=target_type,
        target_id=target_id,
        message=message,
    )
    ActivityRepository(session).add(log)
    await session.flush()
    return log


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ActivityRepository(session)

    async def feed(
        self, *, category: str | None = None, offset: int = 0, limit: int = 50
    ) -> list[ActivityLog]:
        return await self.repository.feed(category=category, offset=offset, limit=limit)
