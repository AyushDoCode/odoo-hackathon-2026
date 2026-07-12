from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.allocations.models import Allocation, AllocationStatus
from app.modules.allocations.repository import AllocationRepository
from app.modules.allocations.schemas import AllocationCreate, TransferRequestCreate
from app.modules.assets.models import AssetStatus
from app.modules.assets.service import AssetConflictError, AssetService
from app.modules.users.models import User, UserRole


class AllocationError(ValueError):
    """Raised for allocation conflicts (already allocated, invalid transition, not found)."""


class AllocationPermissionError(PermissionError):
    """Raised when a Department Head tries to act outside their own department."""


class AllocationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AllocationRepository(session)
        self.assets = AssetService(session)

    async def allocate(self, data: AllocationCreate, *, created_by: UUID) -> Allocation:
        """Race-safe: locks the asset row, verifies it's AVAILABLE, flips it, then records
        the allocation -- all in one transaction. A concurrent allocate() on the same asset
        will block on the row lock and then fail the status check once it proceeds.
        """
        try:
            await self.assets.transition_status(
                data.asset_id,
                AssetStatus.ALLOCATED,
                expected_current={AssetStatus.AVAILABLE},
            )
        except AssetConflictError as exc:
            await self.session.rollback()
            current = await self.repository.get_active_for_asset(data.asset_id)
            holder = current.to_user_id if current else None
            raise AllocationError(
                f"Asset is already allocated (currently held by user {holder}). "
                "Submit a transfer request instead."
            ) from exc

        allocation = Allocation(
            asset_id=data.asset_id,
            to_user_id=data.to_user_id,
            department_id=data.department_id,
            reason=data.reason,
            status=AllocationStatus.ACTIVE,
            allocated_at=datetime.now(UTC),
            expected_return_date=data.expected_return_date,
            created_by=created_by,
        )
        self.repository.add(allocation)
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    async def request_transfer(
        self, asset_id: UUID, data: TransferRequestCreate, *, requested_by: UUID
    ) -> Allocation:
        locked_asset = await self.assets.repository.get_by_id_for_update(asset_id)
        if locked_asset is None:
            await self.session.rollback()
            raise AllocationError("Asset not found")

        allocation = await self.repository.get_active_for_asset(asset_id)
        if allocation is None or allocation.status != AllocationStatus.ACTIVE:
            await self.session.rollback()
            raise AllocationError("Asset has no active allocation to transfer")

        allocation.status = AllocationStatus.TRANSFER_REQUESTED
        allocation.transfer_to_user_id = data.to_user_id
        allocation.reason = data.reason or allocation.reason
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    async def approve_transfer(self, allocation_id: UUID, *, actor: User) -> Allocation:
        allocation = await self.repository.get_by_id(allocation_id)
        if allocation is None or allocation.status != AllocationStatus.TRANSFER_REQUESTED:
            raise AllocationError("Allocation has no pending transfer request")

        if (
            actor.role == UserRole.DEPARTMENT_HEAD
            and actor.department_id != allocation.department_id
        ):
            raise AllocationPermissionError(
                "Department Head may only approve transfers within their own department"
            )

        # Lock the asset row to serialize with any concurrent allocate/return/transfer call.
        await self.assets.repository.get_by_id_for_update(allocation.asset_id)

        now = datetime.now(UTC)
        allocation.status = AllocationStatus.TRANSFER_APPROVED
        allocation.returned_at = now
        allocation.approved_by = actor.id

        new_allocation = Allocation(
            asset_id=allocation.asset_id,
            from_user_id=allocation.to_user_id,
            to_user_id=allocation.transfer_to_user_id,
            department_id=allocation.department_id,
            reason="Transferred",
            status=AllocationStatus.ACTIVE,
            allocated_at=now,
            expected_return_date=allocation.expected_return_date,
            created_by=actor.id,
        )
        self.repository.add(new_allocation)
        await self.session.commit()
        await self.session.refresh(new_allocation)
        return new_allocation

    async def return_asset(
        self, asset_id: UUID, return_condition: str | None, *, actor_id: UUID
    ) -> Allocation:
        try:
            await self.assets.transition_status(
                asset_id, AssetStatus.AVAILABLE, expected_current={AssetStatus.ALLOCATED}
            )
        except AssetConflictError as exc:
            await self.session.rollback()
            raise AllocationError(str(exc)) from exc

        allocation = await self.repository.get_active_for_asset(asset_id)
        if allocation is None:
            await self.session.rollback()
            raise AllocationError("Asset has no active allocation to return")

        allocation.status = AllocationStatus.RETURNED
        allocation.returned_at = datetime.now(UTC)
        allocation.return_condition = return_condition
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    async def history(self, asset_id: UUID) -> list[Allocation]:
        return await self.repository.history_for_asset(asset_id)
