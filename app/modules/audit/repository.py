from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.audit.models import AuditCycle, AuditItem, VerificationResult


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cycle(self, cycle_id: UUID) -> AuditCycle | None:
        statement = (
            select(AuditCycle)
            .options(selectinload(AuditCycle.items).selectinload(AuditItem.asset))
            .where(AuditCycle.id == cycle_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_cycle_locked(self, cycle_id: UUID) -> AuditCycle | None:
        statement = select(AuditCycle).where(AuditCycle.id == cycle_id).with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_cycles(self, *, offset: int = 0, limit: int = 100) -> list[AuditCycle]:
        """Cycle summaries only (no items) -- callers needing item detail should
        fetch the specific cycle via get_cycle()."""
        statement = (
            select(AuditCycle).order_by(AuditCycle.start_date.desc()).offset(offset).limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_item(self, item_id: UUID) -> AuditItem | None:
        statement = (
            select(AuditItem).options(selectinload(AuditItem.asset)).where(AuditItem.id == item_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def items_for_cycle(
        self, cycle_id: UUID, verification: VerificationResult | None = None
    ) -> list[AuditItem]:
        statement = (
            select(AuditItem)
            .options(selectinload(AuditItem.asset))
            .where(AuditItem.cycle_id == cycle_id)
        )
        if verification is not None:
            statement = statement.where(AuditItem.verification == verification)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    def add_cycle(self, cycle: AuditCycle) -> None:
        self.session.add(cycle)

    def add_item(self, item: AuditItem) -> None:
        self.session.add(item)
