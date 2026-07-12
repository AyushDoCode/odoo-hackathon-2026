from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.models import ActivityLog


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, log: ActivityLog) -> None:
        self.session.add(log)

    async def feed(
        self,
        *,
        category: str | None = None,
        recipient_id: UUID | None = None,
        audit_log_only: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ActivityLog]:
        statement = select(ActivityLog).order_by(ActivityLog.created_at.desc())
        if recipient_id is not None:
            statement = statement.where(ActivityLog.recipient_id == recipient_id)
        elif audit_log_only:
            statement = statement.where(ActivityLog.recipient_id.is_(None))
        if category is not None:
            statement = statement.where(ActivityLog.category == category)
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def recent(self, limit: int = 10) -> list[ActivityLog]:
        return await self.feed(limit=limit)

    async def get_for_recipient(self, log_id: UUID, recipient_id: UUID) -> ActivityLog | None:
        statement = select(ActivityLog).where(
            ActivityLog.id == log_id,
            ActivityLog.recipient_id == recipient_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def notification_exists(
        self, *, recipient_id: UUID, action_type: str, target_id: UUID
    ) -> bool:
        statement = select(ActivityLog.id).where(
            ActivityLog.recipient_id == recipient_id,
            ActivityLog.action_type == action_type,
            ActivityLog.target_id == target_id,
        ).limit(1)
        return (await self.session.execute(statement)).scalar_one_or_none() is not None
