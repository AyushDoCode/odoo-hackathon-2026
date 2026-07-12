from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import record as record_activity
from app.modules.assets.models import AssetStatus
from app.modules.assets.service import AssetConflictError, AssetService
from app.modules.maintenance.models import MaintenanceRequest, MaintenanceStatus
from app.modules.maintenance.repository import MaintenanceRepository
from app.modules.maintenance.schemas import MaintenanceRequestCreate


class MaintenanceError(ValueError):
    """Raised for invalid maintenance state transitions."""


class MaintenanceService:
    """Owns every asset-status side effect of the maintenance workflow. Routers must
    never set asset status directly -- only these transition methods may.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = MaintenanceRepository(session)
        self.assets = AssetService(session)

    async def raise_request(
        self, data: MaintenanceRequestCreate, *, created_by: UUID
    ) -> MaintenanceRequest:
        request = MaintenanceRequest(
            asset_id=data.asset_id,
            issue=data.issue,
            priority=data.priority,
            photo_url=data.photo_url,
            status=MaintenanceStatus.PENDING,
            opened_at=datetime.now(UTC),
            created_by=created_by,
        )
        self.repository.add(request)
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def approve(self, request_id: UUID, *, approved_by: UUID) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.PENDING:
            raise MaintenanceError("Request is not pending")

        try:
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
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def assign_technician(
        self, request_id: UUID, technician_id: UUID
    ) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.APPROVED:
            raise MaintenanceError("Request must be APPROVED before assigning a technician")

        request.technician_id = technician_id
        request.status = MaintenanceStatus.TECHNICIAN_ASSIGNED
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def start_progress(self, request_id: UUID) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status != MaintenanceStatus.TECHNICIAN_ASSIGNED:
            raise MaintenanceError("Request must have a technician assigned first")

        request.status = MaintenanceStatus.IN_PROGRESS
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def resolve(self, request_id: UUID) -> MaintenanceRequest:
        request = await self.repository.get_by_id(request_id)
        if request is None or request.status not in {
            MaintenanceStatus.TECHNICIAN_ASSIGNED,
            MaintenanceStatus.IN_PROGRESS,
        }:
            raise MaintenanceError("Request is not in a resolvable state")

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
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def history_for_asset(self, asset_id: UUID) -> list[MaintenanceRequest]:
        return await self.repository.history_for_asset(asset_id)

    async def board(self) -> list[MaintenanceRequest]:
        return await self.repository.board()
