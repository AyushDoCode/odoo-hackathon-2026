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
        offset: int = 0,
        limit: int = 50,
    ) -> list[ActivityLog]:
        statement = select(ActivityLog).order_by(ActivityLog.created_at.desc())
        if category is not None:
            statement = statement.where(ActivityLog.category == category)
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def recent(self, limit: int = 10) -> list[ActivityLog]:
        return await self.feed(limit=limit)
