from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.modules.allocations.models import Allocation, AllocationStatus
from app.modules.assets.models import Asset, AssetStatus


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _eager(self):
        return select(Asset).options(selectinload(Asset.category))

    async def get_by_id(self, asset_id: UUID) -> Asset | None:
        statement = self._eager().where(Asset.id == asset_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, asset_id: UUID) -> Asset | None:
        """Locks the asset row (SELECT ... FOR UPDATE) for race-safe status transitions."""
        statement = select(Asset).where(Asset.id == asset_id).with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_ids(self, asset_ids: list[UUID]) -> list[Asset]:
        if not asset_ids:
            return []
        statement = self._eager().where(Asset.id.in_(asset_ids))
        result = await self.session.execute(statement)
        return list(result.scalars().all())

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
        location: str | None = None,
        visible_to_user_id: UUID | None = None,
        visible_to_department_id: UUID | None = None,
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
                    Asset.location.ilike(like),
                )
            )
        if category_id is not None:
            statement = statement.where(Asset.category_id == category_id)
        if status is not None:
            statement = statement.where(Asset.status == status)
        if location is not None:
            statement = statement.where(Asset.location.ilike(f"%{location.strip()}%"))
        if department_id is not None:
            # "Department" isn't stored on the asset itself -- it's derived from
            # whichever allocation currently holds it (an asset with no active
            # allocation has no department to filter by).
            statement = statement.join(
                Allocation,
                (Allocation.asset_id == Asset.id)
                & Allocation.status.in_(
                    [
                        AllocationStatus.ACTIVE,
                        AllocationStatus.TRANSFER_REQUESTED,
                        AllocationStatus.RETURN_REQUESTED,
                    ]
                )
                & (Allocation.department_id == department_id),
            )
        if visible_to_user_id is not None or visible_to_department_id is not None:
            visible_allocation = aliased(Allocation)
            visibility = [Asset.is_bookable.is_(True)]
            if visible_to_user_id is not None:
                visibility.append(visible_allocation.to_user_id == visible_to_user_id)
            if visible_to_department_id is not None:
                visibility.append(visible_allocation.department_id == visible_to_department_id)
            statement = statement.outerjoin(
                visible_allocation,
                (visible_allocation.asset_id == Asset.id)
                & visible_allocation.status.in_(
                    [
                        AllocationStatus.ACTIVE,
                        AllocationStatus.TRANSFER_REQUESTED,
                        AllocationStatus.RETURN_REQUESTED,
                    ]
                ),
            ).where(or_(*visibility)).distinct()

        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def is_visible_to(
        self,
        asset_id: UUID,
        *,
        user_id: UUID | None = None,
        department_id: UUID | None = None,
    ) -> bool:
        statement = select(Asset.id).outerjoin(
            Allocation,
            (Allocation.asset_id == Asset.id)
            & Allocation.status.in_(
                [
                    AllocationStatus.ACTIVE,
                    AllocationStatus.TRANSFER_REQUESTED,
                    AllocationStatus.RETURN_REQUESTED,
                ]
            ),
        ).where(Asset.id == asset_id)
        visibility = [Asset.is_bookable.is_(True)]
        if user_id is not None:
            visibility.append(Allocation.to_user_id == user_id)
        if department_id is not None:
            visibility.append(Allocation.department_id == department_id)
        statement = statement.where(or_(*visibility)).limit(1)
        return (await self.session.execute(statement)).scalar_one_or_none() is not None

    async def create(self, asset: Asset) -> Asset:
        self.session.add(asset)
        await self.session.flush()
        await self.session.refresh(asset, attribute_names=["category"])
        return asset

    async def count_by_status(self, status: AssetStatus) -> int:
        statement = select(func.count()).select_from(Asset).where(Asset.status == status)
        result = await self.session.execute(statement)
        return int(result.scalar_one())
