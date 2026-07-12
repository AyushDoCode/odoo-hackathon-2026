from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import notify, record as record_activity
from app.modules.allocations.repository import AllocationRepository
from app.modules.allocations.service import AllocationService
from app.modules.assets.models import AssetStatus
from app.modules.assets.service import AssetConflictError, AssetService
from app.modules.maintenance.models import MaintenanceRequest, MaintenanceStatus
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.maintenance.schemas import MaintenanceRequestCreate
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


class MaintenanceError(ValueError):
    """Raised for invalid maintenance state transitions."""


class MaintenancePermissionError(PermissionError):
    """Raised when a caller is not the holder, assignee, or responsible manager."""


class MaintenanceService:
    """Owns every asset-status side effect of the maintenance workflow. Routers must
    never set asset status directly -- only these transition methods may.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = MaintenanceRepository(session)
        self.assets = AssetService(session)
        self.allocations = AllocationRepository(session)
        self.allocation_service = AllocationService(session)
        self.users = UserRepository(session)

    async def raise_request(
        self, data: MaintenanceRequestCreate, *, actor: User
    ) -> MaintenanceRequest:
        asset = await self.assets.get_asset(data.asset_id)
        if asset is None:
            raise MaintenanceError("Asset not found")
        allocation = await self.allocations.get_active_for_asset(data.asset_id)
        if (
            actor.role not in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
            and (allocation is None or allocation.to_user_id != actor.id)
        ):
            raise MaintenancePermissionError(
                "Employees may raise maintenance only for assets allocated to them"
            )
        request = MaintenanceRequest(
            asset_id=data.asset_id,
            issue=data.issue,
            priority=data.priority,
            photo_url=data.photo_url,
            status=MaintenanceStatus.PENDING,
            opened_at=datetime.now(UTC),
            created_by=actor.id,
        )
        self.repository.add(request)
        await self.session.flush()
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="maintenance.requested",
            category="approvals",
            target_type="maintenance_request",
            target_id=request.id,
            message=f"Maintenance requested for asset {data.asset_id}",
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def approve(self, request_id: UUID, *, approved_by: UUID) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.PENDING:
            raise MaintenanceError("Request is not pending")

        try:
            await self.allocation_service.close_for_maintenance(
                request.asset_id, actor_id=approved_by
            )
            await self.assets.transition_status(
                request.asset_id,
                AssetStatus.MAINTENANCE,
                expected_current={
                    AssetStatus.AVAILABLE,
                    AssetStatus.ALLOCATED,
                    AssetStatus.RESERVED,
                },
            )
        except AssetConflictError as exc:
            await self.session.rollback()
            raise MaintenanceError(str(exc)) from exc

        request.status = MaintenanceStatus.APPROVED
        request.approved_by = approved_by
        await record_activity(
            self.session,
            actor_id=approved_by,
            action_type="maintenance.approved",
            category="approvals",
            target_type="maintenance_request",
            target_id=request.id,
            message=f"Maintenance request {request.id} approved",
        )
        if request.created_by is not None:
            await notify(
                self.session,
                recipient_id=request.created_by,
                actor_id=approved_by,
                action_type="maintenance.approved",
                category="approvals",
                target_type="maintenance_request",
                target_id=request.id,
                message=f"Maintenance request {request.id} was approved",
            )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def reject(self, request_id: UUID, *, approved_by: UUID) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.PENDING:
            raise MaintenanceError("Request is not pending")

        request.status = MaintenanceStatus.REJECTED
        request.approved_by = approved_by
        request.resolved_at = datetime.now(UTC)
        await record_activity(
            self.session,
            actor_id=approved_by,
            action_type="maintenance.rejected",
            category="approvals",
            target_type="maintenance_request",
            target_id=request.id,
            message=f"Maintenance request {request.id} rejected",
        )
        if request.created_by is not None:
            await notify(
                self.session,
                recipient_id=request.created_by,
                actor_id=approved_by,
                action_type="maintenance.rejected",
                category="approvals",
                target_type="maintenance_request",
                target_id=request.id,
                message=f"Maintenance request {request.id} was rejected",
            )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def assign_technician(
        self, request_id: UUID, technician_id: UUID
    ) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.APPROVED:
            raise MaintenanceError("Request must be APPROVED before assigning a technician")
        technician = await self.users.get_by_id(technician_id)
        if technician is None or not technician.is_active:
            raise MaintenanceError("Technician must be an active employee")

        request.technician_id = technician_id
        request.status = MaintenanceStatus.TECHNICIAN_ASSIGNED
        await notify(
            self.session,
            recipient_id=technician_id,
            action_type="maintenance.assigned",
            category="alerts",
            target_type="maintenance_request",
            target_id=request.id,
            message=f"You were assigned maintenance request {request.id}",
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    @staticmethod
    def _may_work(request: MaintenanceRequest, actor: User) -> bool:
        return actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER} or request.technician_id == actor.id

    async def start_progress(self, request_id: UUID, *, actor: User) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.TECHNICIAN_ASSIGNED:
            raise MaintenanceError("Request must have a technician assigned first")
        if not self._may_work(request, actor):
            raise MaintenancePermissionError("Only the assigned technician or Asset Manager may start work")

        request.status = MaintenanceStatus.IN_PROGRESS
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="maintenance.in_progress",
            category="alerts",
            target_type="maintenance_request",
            target_id=request.id,
            message=f"Maintenance request {request.id} is in progress",
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def resolve(self, request_id: UUID, *, actor: User) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status not in {
            MaintenanceStatus.TECHNICIAN_ASSIGNED,
            MaintenanceStatus.IN_PROGRESS,
        }:
            raise MaintenanceError("Request is not in a resolvable state")
        if not self._may_work(request, actor):
            raise MaintenancePermissionError("Only the assigned technician or Asset Manager may resolve work")

        try:
            await self.assets.transition_status(
                request.asset_id,
                AssetStatus.AVAILABLE,
                expected_current={AssetStatus.MAINTENANCE},
            )
        except AssetConflictError as exc:
            await self.session.rollback()
            raise MaintenanceError(str(exc)) from exc

        request.status = MaintenanceStatus.RESOLVED
        request.resolved_at = datetime.now(UTC)
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="maintenance.resolved",
            category="alerts",
            target_type="maintenance_request",
            target_id=request.id,
            message=f"Maintenance request {request.id} resolved",
        )
        if request.created_by is not None:
            await notify(
                self.session,
                recipient_id=request.created_by,
                actor_id=actor.id,
                action_type="maintenance.resolved",
                category="alerts",
                target_type="maintenance_request",
                target_id=request.id,
                message=f"Maintenance request {request.id} was resolved",
            )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def history_for_asset(self, asset_id: UUID) -> list[MaintenanceRequest]:
        return await self.repository.history_for_asset(asset_id)

    async def board(self, *, actor: User) -> list[MaintenanceRequest]:
        rows = await self.repository.board()
        if actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}:
            return rows
        return [
            row for row in rows
            if row.created_by == actor.id or row.technician_id == actor.id
        ]
