from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import record as record_activity
from app.modules.assets.models import Asset, AssetStatus
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import AssetCreate, AssetUpdate
from app.modules.users.models import User, UserRole


class AssetConflictError(ValueError):
    """Raised when an asset status transition is not allowed from its current state."""


# Statuses an Admin/Asset Manager may set directly (not driven by another module's
# workflow). ALLOCATED/MAINTENANCE/LOST are owned exclusively by allocations,
# maintenance, and audit respectively and must never be set here.
_MANUALLY_SETTABLE_STATUSES = {
    AssetStatus.AVAILABLE,
    AssetStatus.RESERVED,
    AssetStatus.RETIRED,
    AssetStatus.DISPOSED,
}
_MANUALLY_SETTABLE_FROM = {AssetStatus.AVAILABLE, AssetStatus.RESERVED, AssetStatus.LOST}


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
        location: str | None = None,
        actor: User | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Asset]:
        visible_to_user_id = None
        visible_to_department_id = None
        if actor is not None and actor.role == UserRole.EMPLOYEE:
            visible_to_user_id = actor.id
        elif actor is not None and actor.role == UserRole.DEPARTMENT_HEAD:
            visible_to_department_id = actor.department_id
        return await self.repository.search(
            query=query,
            category_id=category_id,
            status=status,
            department_id=department_id,
            location=location,
            visible_to_user_id=visible_to_user_id,
            visible_to_department_id=visible_to_department_id,
            offset=offset,
            limit=limit,
        )

    async def may_view(self, asset_id: UUID, actor: User) -> bool:
        if actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}:
            return True
        return await self.repository.is_visible_to(
            asset_id,
            user_id=actor.id if actor.role == UserRole.EMPLOYEE else None,
            department_id=actor.department_id if actor.role == UserRole.DEPARTMENT_HEAD else None,
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
                await record_activity(
                    self.session,
                    actor_id=created_by,
                    action_type="asset.registered",
                    category="assets",
                    target_type="asset",
                    target_id=asset.id,
                    message=f"Asset {tag} registered",
                )
                await self.session.commit()
                return asset
            except IntegrityError as exc:
                last_error = exc
                await self.session.rollback()
        raise AssetConflictError("Could not generate a unique asset tag") from last_error

    async def update_asset(
        self, asset: Asset, data: AssetUpdate, *, actor_id: UUID | None = None
    ) -> Asset:
        updates = data.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(asset, field_name, value)
        await record_activity(
            self.session,
            actor_id=actor_id,
            action_type="asset.updated",
            category="assets",
            target_type="asset",
            target_id=asset.id,
            message=f"Asset {asset.tag} updated",
        )
        await self.session.commit()
        await self.session.refresh(asset, attribute_names=["category"])
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

    async def set_manual_status(
        self, asset_id: UUID, new_status: AssetStatus, *, actor_id: UUID | None = None
    ) -> Asset:
        """Admin/Asset Manager directly setting Available/Reserved/Retired/Disposed --
        e.g. reserving an asset for a future purpose outside the booking system, or
        retiring/disposing an asset at end of life. Never used to set ALLOCATED,
        MAINTENANCE, or LOST -- those belong exclusively to their owning workflow.
        """
        if new_status not in _MANUALLY_SETTABLE_STATUSES:
            raise AssetConflictError(
                f"'{new_status}' can only be set by its owning workflow, not manually"
            )
        asset = await self.transition_status(
            asset_id, new_status, expected_current=_MANUALLY_SETTABLE_FROM
        )
        await record_activity(
            self.session,
            actor_id=actor_id,
            action_type="asset.status_changed",
            category="assets",
            target_type="asset",
            target_id=asset.id,
            message=f"Asset {asset.tag} status changed to {new_status.value}",
        )
        await self.session.commit()
        return asset
