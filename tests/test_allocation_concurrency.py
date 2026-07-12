from __future__ import annotations

import asyncio

from app.modules.allocations.schemas import AllocationCreate
from app.modules.allocations.service import AllocationError, AllocationService
from app.modules.assets.models import Asset, AssetStatus

from tests.conftest import cleanup, make_asset, make_user


async def test_two_concurrent_allocations_only_one_succeeds(db_session, session_factory):
    category, asset = await make_asset(db_session, status=AssetStatus.AVAILABLE)
    user_a = await make_user(db_session)
    user_b = await make_user(db_session)
    asset_id, category_id, user_a_id, user_b_id = asset.id, category.id, user_a.id, user_b.id

    async def _allocate(to_user_id):
        async with session_factory() as session:
            service = AllocationService(session)
            data = AllocationCreate(asset_id=asset_id, to_user_id=to_user_id)
            try:
                allocation = await service.allocate(data, created_by=to_user_id)
                return ("ok", allocation)
            except AllocationError as exc:
                return ("error", str(exc))

    try:
        results = await asyncio.gather(_allocate(user_a_id), _allocate(user_b_id))

        outcomes = [r[0] for r in results]
        assert outcomes.count("ok") == 1, f"expected exactly one success, got {outcomes}"
        assert outcomes.count("error") == 1, f"expected exactly one failure, got {outcomes}"

        async with session_factory() as verify_session:
            refreshed = await verify_session.get(Asset, asset_id)
            assert refreshed.status == AssetStatus.ALLOCATED
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session,
                asset_ids=[asset_id],
                category_ids=[category_id],
                user_ids=[user_a_id, user_b_id],
            )


async def test_allocate_already_allocated_asset_requires_transfer(db_session, session_factory):
    category, asset = await make_asset(db_session, status=AssetStatus.AVAILABLE)
    user_a = await make_user(db_session)
    user_b = await make_user(db_session)
    asset_id, category_id, user_a_id, user_b_id = asset.id, category.id, user_a.id, user_b.id

    try:
        service = AllocationService(db_session)
        await service.allocate(
            AllocationCreate(asset_id=asset_id, to_user_id=user_a_id), created_by=user_a_id
        )

        try:
            await service.allocate(
                AllocationCreate(asset_id=asset_id, to_user_id=user_b_id), created_by=user_b_id
            )
            assert False, "expected AllocationError for already-allocated asset"
        except AllocationError as exc:
            assert "transfer request" in str(exc).lower()
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session,
                asset_ids=[asset_id],
                category_ids=[category_id],
                user_ids=[user_a_id, user_b_id],
            )
