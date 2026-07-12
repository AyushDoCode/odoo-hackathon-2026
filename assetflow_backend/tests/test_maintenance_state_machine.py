from __future__ import annotations

from app.modules.assets.models import AssetStatus
from app.modules.maintenance.models import MaintenanceStatus
from app.modules.maintenance.schemas import MaintenanceRequestCreate
from app.modules.maintenance.service import MaintenanceError, MaintenanceService

from tests.conftest import cleanup, make_asset, make_user


async def test_approve_sets_asset_maintenance_and_resolve_restores_available(
    db_session, session_factory
):
    category, asset = await make_asset(db_session, status=AssetStatus.AVAILABLE)
    manager = await make_user(db_session)
    technician = await make_user(db_session)
    asset_id, category_id = asset.id, category.id
    manager_id, technician_id = manager.id, technician.id

    try:
        service = MaintenanceService(db_session)
        request = await service.raise_request(
            MaintenanceRequestCreate(asset_id=asset_id, issue="Bulb not turning on"),
            created_by=manager_id,
        )
        assert request.status == MaintenanceStatus.PENDING

        approved = await service.approve(request.id, approved_by=manager_id)
        assert approved.status == MaintenanceStatus.APPROVED

        # transition_status flushes within the same session, so `asset` (same identity
        # map) already reflects the new status -- no manual expire/reload needed.
        assert asset.status == AssetStatus.MAINTENANCE

        assigned = await service.assign_technician(request.id, technician_id)
        assert assigned.status == MaintenanceStatus.TECHNICIAN_ASSIGNED

        in_progress = await service.start_progress(request.id)
        assert in_progress.status == MaintenanceStatus.IN_PROGRESS

        resolved = await service.resolve(request.id)
        assert resolved.status == MaintenanceStatus.RESOLVED
        assert resolved.resolved_at is not None
        assert asset.status == AssetStatus.AVAILABLE
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session,
                asset_ids=[asset_id],
                category_ids=[category_id],
                user_ids=[manager_id, technician_id],
            )


async def test_reject_leaves_asset_status_untouched(db_session, session_factory):
    category, asset = await make_asset(db_session, status=AssetStatus.AVAILABLE)
    manager = await make_user(db_session)
    asset_id, category_id, manager_id = asset.id, category.id, manager.id

    try:
        service = MaintenanceService(db_session)
        request = await service.raise_request(
            MaintenanceRequestCreate(asset_id=asset_id, issue="Squeaky wheel"),
            created_by=manager_id,
        )
        rejected = await service.reject(request.id, approved_by=manager_id)
        assert rejected.status == MaintenanceStatus.REJECTED
        assert asset.status == AssetStatus.AVAILABLE

        try:
            await service.approve(request.id, approved_by=manager_id)
            assert False, "expected MaintenanceError: cannot approve a rejected request"
        except MaintenanceError:
            pass
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session,
                asset_ids=[asset_id],
                category_ids=[category_id],
                user_ids=[manager_id],
            )
