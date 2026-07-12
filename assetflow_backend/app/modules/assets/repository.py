from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.assets.models import Asset, AssetStatus


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _eager(self):
        return select(Asset).options(
            selectinload(Asset.category), selectinload(Asset.department)
        )

    async def get_by_id(self, asset_id: UUID) -> Asset | None:
        statement = self._eager().where(Asset.id == asset_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, asset_id: UUID) -> Asset | None:
        """Locks the asset row (SELECT ... FOR UPDATE) for race-safe status transitions."""
        statement = select(Asset).where(Asset.id == asset_id).with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_tag(self, tag: str) -> Asset | None:
        statement = self._eager().where(Asset.tag == tag)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def next_tag_sequence(self) -> int:
        statement = select(func.count()).select_from(Asset)
        result = await self.session.execute(statement)
        return int(result.scalar_one()) + 1

    async def search(
        self,
        *,
        query: str | None = None,
        category_id: UUID | None = None,
        status: AssetStatus | None = None,
        department_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Asset]:
        statement = self._eager()

        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    Asset.tag.ilike(like),
                    Asset.serial_number.ilike(like),
                    Asset.qr_code.ilike(like),
                )
            )
        if category_id is not None:
            statement = statement.where(Asset.category_id == category_id)
        if status is not None:
            statement = statement.where(Asset.status == status)
        if department_id is not None:
            statement = statement.where(Asset.department_id == department_id)

        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, asset: Asset) -> Asset:
        self.session.add(asset)
        await self.session.flush()
        await self.session.refresh(asset, attribute_names=["category", "department"])
        return asset

    async def count_by_status(self, status: AssetStatus) -> int:
        statement = select(func.count()).select_from(Asset).where(Asset.status == status)
        result = await self.session.execute(statement)
        return int(result.scalar_one())
