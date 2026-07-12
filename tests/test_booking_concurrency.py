from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.modules.bookings.schemas import BookingCreate
from app.modules.bookings.service import BookingError, BookingService

from tests.conftest import cleanup, make_asset, make_user

# MySQL's DATETIME column has no fractional-second component by default, so any
# microseconds in Python datetimes get silently truncated on write. Tests must use
# whole-second timestamps or an exact boundary comparison (e.g. back-to-back slots)
# can appear to mismatch against what's actually stored.
_NOW = datetime.now(UTC).replace(microsecond=0)


async def test_two_concurrent_overlapping_bookings_only_one_succeeds(db_session, session_factory):
    category, asset = await make_asset(db_session, is_bookable=True)
    user_a = await make_user(db_session)
    user_b = await make_user(db_session)
    asset_id, category_id, user_a_id, user_b_id = asset.id, category.id, user_a.id, user_b.id

    start = _NOW + timedelta(days=1)
    end = start + timedelta(hours=1)
    # Overlapping window: starts 30 minutes into the first booking.
    overlapping_start = start + timedelta(minutes=30)
    overlapping_end = overlapping_start + timedelta(hours=1)

    async def _book(user, window_start, window_end):
        async with session_factory() as session:
            service = BookingService(session)
            data = BookingCreate(
                resource_id=asset_id,
                start_time=window_start,
                end_time=window_end,
                purpose="test",
            )
            try:
                booking = await service.create_booking(data, actor=user)
                return ("ok", booking)
            except BookingError as exc:
                return ("error", str(exc))

    try:
        results = await asyncio.gather(
            _book(user_a, start, end),
            _book(user_b, overlapping_start, overlapping_end),
        )

        outcomes = [r[0] for r in results]
        assert outcomes.count("ok") == 1, f"expected exactly one success, got {outcomes}"
        assert outcomes.count("error") == 1, f"expected exactly one failure, got {outcomes}"
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session,
                asset_ids=[asset_id],
                category_ids=[category_id],
                user_ids=[user_a_id, user_b_id],
            )


async def test_back_to_back_bookings_do_not_overlap(db_session, session_factory):
    category, asset = await make_asset(db_session, is_bookable=True)
    user_a = await make_user(db_session)
    asset_id, category_id, user_a_id = asset.id, category.id, user_a.id

    start = _NOW + timedelta(days=2)
    end = start + timedelta(hours=1)
    next_start = end
    next_end = next_start + timedelta(hours=1)

    try:
        service = BookingService(db_session)
        first = await service.create_booking(
            BookingCreate(resource_id=asset_id, start_time=start, end_time=end),
            actor=user_a,
        )
        second = await service.create_booking(
            BookingCreate(resource_id=asset_id, start_time=next_start, end_time=next_end),
            actor=user_a,
        )
        assert first.id != second.id
    finally:
        async with session_factory() as cleanup_session:
            await cleanup(
                cleanup_session, asset_ids=[asset_id], category_ids=[category_id], user_ids=[user_a_id]
            )
