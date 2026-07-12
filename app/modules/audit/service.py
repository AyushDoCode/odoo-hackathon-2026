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
from app.modules.users.repository import UserRepository


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
        self.users = UserRepository(session)

    async def create_cycle(
        self, data: AuditCycleCreate, *, created_by: UUID
    ) -> AuditCycle:
        found_assets = await self.asset_repository.get_by_ids(data.asset_ids)
        found_asset_ids = {asset.id for asset in found_assets}
        missing_assets = set(data.asset_ids) - found_asset_ids
        if missing_assets:
            raise AuditError(f"Asset(s) not found: {', '.join(str(i) for i in missing_assets)}")
        assets = {asset.id: asset for asset in found_assets}

        found_auditor_ids = await self.users.existing_ids(data.auditor_ids)
        missing_auditors = set(data.auditor_ids) - found_auditor_ids
        if missing_auditors:
            raise AuditError(
                f"Auditor(s) not found: {', '.join(str(i) for i in missing_auditors)}"
            )

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

        # Locks the cycle row so a concurrent close_cycle() can't finish (and act on
        # a stale item list) while this verification is still being written.
        cycle = await self.repository.get_cycle_locked(item.cycle_id)
        if cycle is None:
            await self.session.rollback()
            raise AuditError("Audit cycle not found")
        if cycle.status == AuditCycleStatus.CLOSED:
            await self.session.rollback()
            raise AuditError("Audit cycle is closed and locked")
        if actor.role != UserRole.ADMIN and str(actor.id) not in cycle.auditor_ids:
            await self.session.rollback()
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
        await self.session.refresh(item, attribute_names=["asset"])
        return item

    async def approve_discrepancy(
        self, item_id: UUID, data: DiscrepancyResolution, *, actor: User
    ) -> AuditItem:
        item = await self.repository.get_item(item_id)
        if item is None:
            raise AuditError("Audit item not found")
        cycle = await self.repository.get_cycle_locked(item.cycle_id)
        if cycle is None or cycle.status == AuditCycleStatus.CLOSED:
            await self.session.rollback()
            raise AuditError("Audit cycle is closed or missing")
        if item.verification not in {VerificationResult.MISSING, VerificationResult.DAMAGED}:
            await self.session.rollback()
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
        await self.session.refresh(item, attribute_names=["asset"])
        return item

    async def close_cycle(self, cycle_id: UUID, *, actor_id: UUID) -> AuditCycle:
        cycle = await self.repository.get_cycle_locked(cycle_id)
        if cycle is None:
            await self.session.rollback()
            raise AuditError("Audit cycle not found")
        if cycle.status == AuditCycleStatus.CLOSED:
            await self.session.rollback()
            raise AuditError("Audit cycle is already closed")

        items = await self.repository.items_for_cycle(cycle_id)
        if any(item.verification is None for item in items):
            await self.session.rollback()
            raise AuditError("Every asset must be verified before closing the audit cycle")
        unresolved = [
            item for item in items
            if item.verification in {VerificationResult.MISSING, VerificationResult.DAMAGED}
            and item.resolution_approved_by is None
        ]
        if unresolved:
            await self.session.rollback()
            raise AuditError("Every discrepancy must be approved by an Asset Manager before closing")
        for item in items:
            if item.verification == VerificationResult.MISSING:
                await self.allocation_service.close_for_maintenance(
                    item.asset_id,
                    actor_id=item.resolution_approved_by or cycle.created_by,
                    reason=f"Automatically checked in: asset confirmed missing in audit cycle {cycle_id}",
                )
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
                    await self.session.rollback()
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
                    await self.session.rollback()
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

    async def list_cycles(self, *, actor: User, offset: int = 0, limit: int = 100) -> list[AuditCycle]:
        cycles = await self.repository.list_cycles(offset=offset, limit=limit)
        return [cycle for cycle in cycles if self.may_view_cycle(cycle, actor)]

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
