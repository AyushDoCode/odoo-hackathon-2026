from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.allocations.models import Allocation, AllocationStatus


class AllocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, allocation_id: UUID) -> Allocation | None:
        return await self.session.get(Allocation, allocation_id)

    async def get_active_for_asset(self, asset_id: UUID) -> Allocation | None:
        """The single ACTIVE or TRANSFER_REQUESTED allocation row for an asset, if any."""
        statement = select(Allocation).where(
            Allocation.asset_id == asset_id,
            Allocation.status.in_(
                [
                    AllocationStatus.ACTIVE,
                    AllocationStatus.TRANSFER_REQUESTED,
                    AllocationStatus.RETURN_REQUESTED,
                ]
            ),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def history_for_asset(self, asset_id: UUID) -> list[Allocation]:
        statement = (
            select(Allocation)
            .where(Allocation.asset_id == asset_id)
            .order_by(Allocation.allocated_at.desc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def overdue(self, *, as_of) -> list[Allocation]:
        statement = select(Allocation).where(
            Allocation.status == AllocationStatus.ACTIVE,
            Allocation.expected_return_date.is_not(None),
            Allocation.expected_return_date < as_of,
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def upcoming_returns(self, *, as_of, within_days: int):
        from datetime import timedelta

        statement = select(Allocation).where(
            Allocation.status == AllocationStatus.ACTIVE,
            Allocation.expected_return_date.is_not(None),
            Allocation.expected_return_date >= as_of,
            Allocation.expected_return_date <= as_of + timedelta(days=within_days),
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    def add(self, allocation: Allocation) -> None:
        self.session.add(allocation)

    async def count_by_status(self, status: AllocationStatus) -> int:
        statement = select(func.count()).select_from(Allocation).where(Allocation.status == status)
        result = await self.session.execute(statement)
        return int(result.scalar_one())
