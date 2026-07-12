from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.models import AssetCategory


class AssetCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, category_id: UUID) -> AssetCategory | None:
        return await self.session.get(AssetCategory, category_id)

    async def get_by_name(self, name: str) -> AssetCategory | None:
        statement = select(AssetCategory).where(AssetCategory.name == name.strip())
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[AssetCategory]:
        statement = select(AssetCategory).offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def create(self, category: AssetCategory) -> AssetCategory:
        self.session.add(category)
        await self.session.flush()
        await self.session.refresh(category)
        return category

    async def delete(self, category: AssetCategory) -> None:
        await self.session.delete(category)
