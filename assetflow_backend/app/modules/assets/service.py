from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assets.models import Asset, AssetStatus
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import AssetCreate, AssetUpdate


class AssetConflictError(ValueError):
    """Raised when an asset status transition is not allowed from its current state."""


class AssetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AssetRepository(session)

    async def get_asset(self, asset_id: UUID) -> Asset | None:
        return await self.repository.get_by_id(asset_id)

    async def search_assets(
        self,
        *,
        query: str | None = None,
        category_id: UUID | None = None,
        status: AssetStatus | None = None,
        department_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Asset]:
        return await self.repository.search(
            query=query,
            category_id=category_id,
            status=status,
            department_id=department_id,
            offset=offset,
            limit=limit,
        )

    async def create_asset(self, data: AssetCreate, *, created_by: UUID | None) -> Asset:
        # Retry a handful of times in case of a concurrent tag collision.
        last_error: IntegrityError | None = None
        for _ in range(5):
            sequence = await self.repository.next_tag_sequence()
            tag = f"AF-{sequence:04d}"
            asset = Asset(
                tag=tag,
                created_by=created_by,
                **data.model_dump(),
            )
            try:
                asset = await self.repository.create(asset)
                await self.session.commit()
                return asset
            except IntegrityError as exc:
                last_error = exc
                await self.session.rollback()
        raise AssetConflictError("Could not generate a unique asset tag") from last_error

    async def update_asset(self, asset: Asset, data: AssetUpdate) -> Asset:
        updates = data.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(asset, field_name, value)
        await self.session.commit()
        await self.session.refresh(asset, attribute_names=["category", "department"])
        return asset

    async def transition_status(
        self,
        asset_id: UUID,
        new_status: AssetStatus,
        *,
        expected_current: set[AssetStatus] | None = None,
    ) -> Asset:
        """Race-safe status transition: locks the asset row, verifies current state, flips it.

        Callers (allocations/maintenance/audit services) must call this from within their
        own open transaction and commit once all their own changes are also staged.
        """
        asset = await self.repository.get_by_id_for_update(asset_id)
        if asset is None:
            raise AssetConflictError(f"Asset {asset_id} not found")
        if expected_current is not None and asset.status not in expected_current:
            raise AssetConflictError(
                f"Asset {asset_id} is '{asset.status}', expected one of {expected_current}"
            )
        asset.status = new_status
        await self.session.flush()
        return asset
