from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import record as record_activity
from app.modules.allocations.service import AllocationService
from app.modules.assets.models import AssetStatus
from app.modules.assets.repository import AssetRepository
from app.modules.assets.service import AssetConflictError, AssetService
from app.modules.audit.models import AuditCycle, AuditCycleStatus, AuditItem, VerificationResult
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import (
    AuditCycleCreate,
    AuditItemVerify,
    DiscrepancyReport,
    DiscrepancyResolution,
)
from app.modules.users.models import User, UserRole


class AuditError(ValueError):
    """Raised for invalid audit cycle operations."""


class AuditPermissionError(PermissionError):
    """Raised when a caller who is not an assigned auditor (or admin) tries to verify."""


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuditRepository(session)
        self.assets = AssetService(session)
        self.asset_repository = AssetRepository(session)
        self.allocation_service = AllocationService(session)

    async def create_cycle(
        self, data: AuditCycleCreate, *, created_by: UUID
    ) -> AuditCycle:
        assets = {}
        for asset_id in data.asset_ids:
            asset = await self.asset_repository.get_by_id(asset_id)
            if asset is None:
                raise AuditError(f"Asset {asset_id} not found")
            assets[asset_id] = asset

        cycle = AuditCycle(
            department_id=data.department_id,
            location=data.location,
            start_date=data.start_date,
            end_date=data.end_date,
            auditor_ids=[str(uid) for uid in data.auditor_ids],
            status=AuditCycleStatus.OPEN,
            created_by=created_by,
        )
        self.repository.add_cycle(cycle)
        await self.session.flush()

        for asset_id in data.asset_ids:
            asset = assets[asset_id]
            item = AuditItem(
                cycle_id=cycle.id,
                asset_id=asset_id,
                expected_location=asset.location if asset else None,
                created_by=created_by,
            )
            self.repository.add_item(item)

        await record_activity(
            self.session,
            actor_id=created_by,
            action_type="audit.cycle_created",
            category="audit",
            target_type="audit_cycle",
            target_id=cycle.id,
            message=f"Audit cycle {cycle.id} created",
        )

        await self.session.commit()
        return await self.repository.get_cycle(cycle.id)

    async def verify_item(
        self, item_id: UUID, data: AuditItemVerify, *, actor: User
    ) -> AuditItem:
        item = await self.repository.get_item(item_id)
        if item is None:
            raise AuditError("Audit item not found")

        cycle = await self.repository.get_cycle(item.cycle_id)
        if cycle is None:
            raise AuditError("Audit cycle not found")
        if cycle.status == AuditCycleStatus.CLOSED:
            raise AuditError("Audit cycle is closed and locked")
        if actor.role != UserRole.ADMIN and str(actor.id) not in cycle.auditor_ids:
            raise AuditPermissionError("You are not an assigned auditor for this cycle")

        item.verification = data.verification
        item.notes = data.notes
        item.resolution_notes = None
        item.resolution_approved_by = None
        item.resolution_approved_at = None
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="audit.item_verified",
            category="audit",
            target_type="audit_item",
            target_id=item.id,
            message=f"Audit item {item.id} marked {data.verification.value}",
        )
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def approve_discrepancy(
        self, item_id: UUID, data: DiscrepancyResolution, *, actor: User
    ) -> AuditItem:
        item = await self.repository.get_item(item_id)
        if item is None:
            raise AuditError("Audit item not found")
        cycle = await self.repository.get_cycle(item.cycle_id)
        if cycle is None or cycle.status == AuditCycleStatus.CLOSED:
            raise AuditError("Audit cycle is closed or missing")
        if item.verification not in {VerificationResult.MISSING, VerificationResult.DAMAGED}:
            raise AuditError("Only missing or damaged items require discrepancy resolution")
        item.resolution_notes = data.resolution_notes
        item.resolution_approved_by = actor.id
        item.resolution_approved_at = datetime.now(UTC)
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="audit.discrepancy_approved",
            category="approvals",
            target_type="audit_item",
            target_id=item.id,
            message=f"Discrepancy resolution approved for audit item {item.id}",
        )
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def close_cycle(self, cycle_id: UUID, *, actor_id: UUID) -> AuditCycle:
        cycle = await self.repository.get_cycle_locked(cycle_id)
        if cycle is None:
            raise AuditError("Audit cycle not found")
        if cycle.status == AuditCycleStatus.CLOSED:
            raise AuditError("Audit cycle is already closed")

        items = await self.repository.items_for_cycle(cycle_id)
        if any(item.verification is None for item in items):
            raise AuditError("Every asset must be verified before closing the audit cycle")
        unresolved = [
            item for item in items
            if item.verification in {VerificationResult.MISSING, VerificationResult.DAMAGED}
            and item.resolution_approved_by is None
        ]
        if unresolved:
            raise AuditError("Every discrepancy must be approved by an Asset Manager before closing")
        for item in items:
            if item.verification == VerificationResult.MISSING:
                try:
                    await self.assets.transition_status(
                        item.asset_id,
                        AssetStatus.LOST,
                        expected_current={
                            AssetStatus.AVAILABLE,
                            AssetStatus.ALLOCATED,
                            AssetStatus.RESERVED,
                            AssetStatus.MAINTENANCE,
                            AssetStatus.LOST,
                        },
                    )
                except AssetConflictError as exc:
                    raise AuditError(str(exc)) from exc
                await record_activity(
                    self.session,
                    actor_id=cycle.created_by,
                    action_type="audit.discrepancy_flagged",
                    category="alerts",
                    target_type="asset",
                    target_id=item.asset_id,
                    message=f"Audit cycle {cycle_id}: asset {item.asset_id} missing",
                )
            elif item.verification == VerificationResult.DAMAGED:
                await self.allocation_service.close_for_maintenance(
                    item.asset_id, actor_id=item.resolution_approved_by or cycle.created_by
                )
                try:
                    await self.assets.transition_status(
                        item.asset_id,
                        AssetStatus.MAINTENANCE,
                        expected_current={
                            AssetStatus.AVAILABLE,
                            AssetStatus.ALLOCATED,
                            AssetStatus.RESERVED,
                            AssetStatus.MAINTENANCE,
                        },
                    )
                except AssetConflictError as exc:
                    raise AuditError(str(exc)) from exc
                await record_activity(
                    self.session,
                    actor_id=cycle.created_by,
                    action_type="audit.discrepancy_flagged",
                    category="alerts",
                    target_type="asset",
                    target_id=item.asset_id,
                    message=f"Audit cycle {cycle_id}: asset {item.asset_id} damaged",
                )

        cycle.status = AuditCycleStatus.CLOSED
        await record_activity(
            self.session,
            actor_id=actor_id,
            action_type="audit.cycle_closed",
            category="audit",
            target_type="audit_cycle",
            target_id=cycle.id,
            message=f"Audit cycle {cycle.id} closed",
        )
        await self.session.commit()
        return await self.repository.get_cycle(cycle_id)

    async def discrepancy_report(self, cycle_id: UUID) -> DiscrepancyReport:
        missing = await self.repository.items_for_cycle(cycle_id, VerificationResult.MISSING)
        damaged = await self.repository.items_for_cycle(cycle_id, VerificationResult.DAMAGED)
        return DiscrepancyReport(cycle_id=cycle_id, missing=missing, damaged=damaged)

    async def get_cycle(self, cycle_id: UUID) -> AuditCycle | None:
        return await self.repository.get_cycle(cycle_id)

    @staticmethod
    def may_view_cycle(cycle: AuditCycle, actor: User) -> bool:
        return (
            actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
            or str(actor.id) in cycle.auditor_ids
            or (
                actor.role == UserRole.DEPARTMENT_HEAD
                and actor.department_id is not None
                and actor.department_id == cycle.department_id
            )
        )
