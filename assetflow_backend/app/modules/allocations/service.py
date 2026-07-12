from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import notify, record as record_activity
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
        if data.to_user_id is None and data.department_id is None:
            raise AllocationError("Allocation requires an employee or department")
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
        await record_activity(
            self.session,
            actor_id=created_by,
            action_type="asset.allocated",
            category="alerts",
            target_type="asset",
            target_id=data.asset_id,
            message=f"Asset {data.asset_id} allocated to user {data.to_user_id}",
        )
        if data.to_user_id is not None:
            await notify(
                self.session,
                recipient_id=data.to_user_id,
                actor_id=created_by,
                action_type="asset.assigned",
                category="alerts",
                target_type="asset",
                target_id=data.asset_id,
                message=f"Asset {data.asset_id} was assigned to you",
            )
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    @staticmethod
    def _may_request(allocation: Allocation, actor: User) -> bool:
        return (
            actor.id == allocation.to_user_id
            or actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
            or (
                actor.role == UserRole.DEPARTMENT_HEAD
                and actor.department_id is not None
                and actor.department_id == allocation.department_id
            )
        )

    async def request_transfer(
        self, asset_id: UUID, data: TransferRequestCreate, *, actor: User
    ) -> Allocation:
        locked_asset = await self.assets.repository.get_by_id_for_update(asset_id)
        if locked_asset is None:
            await self.session.rollback()
            raise AllocationError("Asset not found")

        allocation = await self.repository.get_active_for_asset(asset_id)
        if allocation is None or allocation.status != AllocationStatus.ACTIVE:
            await self.session.rollback()
            raise AllocationError("Asset has no active allocation to transfer")
        if not self._may_request(allocation, actor):
            await self.session.rollback()
            raise AllocationPermissionError("Only the holder or responsible manager may request transfer")
        if allocation.to_user_id == data.to_user_id:
            await self.session.rollback()
            raise AllocationError("Transfer target must be different from the current holder")

        allocation.status = AllocationStatus.TRANSFER_REQUESTED
        allocation.transfer_to_user_id = data.to_user_id
        allocation.reason = data.reason or allocation.reason
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="transfer.requested",
            category="approvals",
            target_type="allocation",
            target_id=allocation.id,
            message=f"Transfer requested for asset {asset_id}",
        )
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    async def approve_transfer(self, allocation_id: UUID, *, actor: User) -> Allocation:
        allocation = await self.repository.get_by_id_for_update(allocation_id)
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
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="transfer.approved",
            category="approvals",
            target_type="asset",
            target_id=allocation.asset_id,
            message=f"Transfer of asset {allocation.asset_id} approved by {actor.id}",
        )
        if new_allocation.to_user_id is not None:
            await notify(
                self.session,
                recipient_id=new_allocation.to_user_id,
                actor_id=actor.id,
                action_type="transfer.approved",
                category="approvals",
                target_type="allocation",
                target_id=new_allocation.id,
                message=f"Transfer approved: asset {allocation.asset_id} is assigned to you",
            )
        await self.session.commit()
        await self.session.refresh(new_allocation)
        return new_allocation

    async def request_return(
        self, asset_id: UUID, return_condition: str | None, *, actor: User
    ) -> Allocation:
        await self.assets.repository.get_by_id_for_update(asset_id)
        allocation = await self.repository.get_active_for_asset(asset_id)
        if allocation is None or allocation.status != AllocationStatus.ACTIVE:
            await self.session.rollback()
            raise AllocationError("Asset has no active allocation to return")
        if not self._may_request(allocation, actor):
            await self.session.rollback()
            raise AllocationPermissionError("Only the holder or responsible manager may request return")
        allocation.status = AllocationStatus.RETURN_REQUESTED
        allocation.return_condition = return_condition
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="return.requested",
            category="approvals",
            target_type="allocation",
            target_id=allocation.id,
            message=f"Return requested for asset {asset_id}",
        )
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    async def approve_return(self, allocation_id: UUID, *, actor_id: UUID) -> Allocation:
        allocation = await self.repository.get_by_id(allocation_id)
        if allocation is None or allocation.status != AllocationStatus.RETURN_REQUESTED:
            raise AllocationError("Allocation has no pending return request")
        try:
            await self.assets.transition_status(
                allocation.asset_id,
                AssetStatus.AVAILABLE,
                expected_current={AssetStatus.ALLOCATED},
            )
        except AssetConflictError as exc:
            await self.session.rollback()
            raise AllocationError(str(exc)) from exc

        allocation.status = AllocationStatus.RETURNED
        allocation.returned_at = datetime.now(UTC)
        allocation.approved_by = actor_id
        await record_activity(
            self.session,
            actor_id=actor_id,
            action_type="return.approved",
            category="approvals",
            target_type="allocation",
            target_id=allocation.id,
            message=f"Return approved for asset {allocation.asset_id}",
        )
        if allocation.to_user_id is not None:
            await notify(
                self.session,
                recipient_id=allocation.to_user_id,
                actor_id=actor_id,
                action_type="return.approved",
                category="approvals",
                target_type="allocation",
                target_id=allocation.id,
                message=f"Return approved for asset {allocation.asset_id}",
            )
        await self.session.commit()
        await self.session.refresh(allocation)
        return allocation

    async def close_for_maintenance(
        self, asset_id: UUID, *, actor_id: UUID, reason: str = "Automatically checked in for approved maintenance"
    ) -> None:
        allocation = await self.repository.get_active_for_asset(asset_id)
        if allocation is None:
            return
        allocation.status = AllocationStatus.RETURNED
        allocation.returned_at = datetime.now(UTC)
        allocation.return_condition = reason
        allocation.approved_by = actor_id
        await self.session.flush()

    async def history(self, asset_id: UUID) -> list[Allocation]:
        return await self.repository.history_for_asset(asset_id)
