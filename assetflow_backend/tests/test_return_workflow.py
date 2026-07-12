from __future__ import annotations

from app.modules.allocations.models import AllocationStatus
from app.modules.allocations.schemas import AllocationCreate
from app.modules.allocations.service import AllocationService
from app.modules.assets.models import AssetStatus
from app.modules.users.models import UserRole

from tests.conftest import cleanup, make_asset, make_user


async def test_return_requires_request_then_manager_approval(db_session, session_factory):
    category, asset = await make_asset(db_session, status=AssetStatus.AVAILABLE)
    employee = await make_user(db_session)
    manager = await make_user(db_session, role=UserRole.ASSET_MANAGER)
    asset_id, category_id = asset.id, category.id

    try:
        service = AllocationService(db_session)
        allocation = await service.allocate(
            AllocationCreate(asset_id=asset_id, to_user_id=employee.id),
            created_by=manager.id,
        )
        requested = await service.request_return(
            asset_id, "Good condition", actor=employee
        )
        assert requested.id == allocation.id
        assert requested.status == AllocationStatus.RETURN_REQUESTED
        assert asset.status == AssetStatus.ALLOCATED

        approved = await service.approve_return(allocation.id, actor_id=manager.id)
        assert approved.status == AllocationStatus.RETURNED
        assert approved.approved_by == manager.id
        assert asset.status == AssetStatus.AVAILABLE
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session,
                asset_ids=[asset_id],
                category_ids=[category_id],
                user_ids=[employee.id, manager.id],
            )
