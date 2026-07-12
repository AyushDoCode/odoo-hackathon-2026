from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import MaintenanceRequest, MaintenanceStatus


class MaintenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, request_id: UUID) -> MaintenanceRequest | None:
        return await self.session.get(MaintenanceRequest, request_id)

    async def get_by_id_for_update(self, request_id: UUID) -> MaintenanceRequest | None:
        """Locks the request row (SELECT ... FOR UPDATE) so concurrent transitions on
        the same request (e.g. approve vs. reject) serialize instead of racing.
        """
        statement = select(MaintenanceRequest).where(
            MaintenanceRequest.id == request_id
        ).with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def history_for_asset(self, asset_id: UUID) -> list[MaintenanceRequest]:
        statement = (
            select(MaintenanceRequest)
            .where(MaintenanceRequest.asset_id == asset_id)
            .order_by(MaintenanceRequest.opened_at.desc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def by_status(self, status_: MaintenanceStatus) -> list[MaintenanceRequest]:
        statement = select(MaintenanceRequest).where(MaintenanceRequest.status == status_)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def board(self) -> list[MaintenanceRequest]:
        """All non-terminal-history rows for the kanban view."""
        statement = select(MaintenanceRequest).order_by(MaintenanceRequest.opened_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    def add(self, request: MaintenanceRequest) -> None:
        self.session.add(request)
