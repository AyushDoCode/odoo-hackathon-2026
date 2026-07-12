from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.models import AssetCategory
from app.modules.categories.repository import AssetCategoryRepository
from app.modules.categories.schemas import AssetCategoryCreate, AssetCategoryUpdate


class AssetCategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AssetCategoryRepository(session)

    async def get_category(self, category_id: UUID) -> AssetCategory | None:
        return await self.repository.get_by_id(category_id)

    async def get_category_by_name(self, name: str) -> AssetCategory | None:
        return await self.repository.get_by_name(name)

    async def list_categories(self, *, offset: int = 0, limit: int = 100) -> list[AssetCategory]:
        return await self.repository.list(offset=offset, limit=limit)

    async def create_category(self, data: AssetCategoryCreate) -> AssetCategory:
        category = AssetCategory(**data.model_dump())
        category = await self.repository.create(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def update_category(self, category: AssetCategory, data: AssetCategoryUpdate) -> AssetCategory:
        updates = data.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(category, field_name, value)

        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete_category(self, category: AssetCategory) -> None:
        await self.repository.delete(category)
        await self.session.commit()
