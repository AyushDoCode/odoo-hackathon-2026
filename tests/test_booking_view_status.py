from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.bookings.models import BookingStatus
from app.modules.bookings.schemas import BookingRead, BookingViewStatus


def _booking_payload(start: datetime, end: datetime, status: BookingStatus) -> dict:
    now = datetime.now(UTC)
    user_id = uuid4()
    return {
        "id": uuid4(),
        "resource_id": uuid4(),
        "user_id": user_id,
        "department_id": None,
        "start_time": start,
        "end_time": end,
        "purpose": None,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "created_by": user_id,
    }


def test_booking_status_is_derived_from_time_and_cancellation() -> None:
    now = datetime.now(UTC)
    upcoming = BookingRead.model_validate(
        _booking_payload(now + timedelta(hours=1), now + timedelta(hours=2), BookingStatus.BOOKED)
    )
    ongoing = BookingRead.model_validate(
        _booking_payload(now - timedelta(minutes=5), now + timedelta(minutes=5), BookingStatus.BOOKED)
    )
    completed = BookingRead.model_validate(
        _booking_payload(now - timedelta(hours=2), now - timedelta(hours=1), BookingStatus.BOOKED)
    )
    cancelled = BookingRead.model_validate(
        _booking_payload(now + timedelta(hours=1), now + timedelta(hours=2), BookingStatus.CANCELLED)
    )

    assert upcoming.status == BookingViewStatus.UPCOMING
    assert ongoing.status == BookingViewStatus.ONGOING
    assert completed.status == BookingViewStatus.COMPLETED
    assert cancelled.status == BookingViewStatus.CANCELLED
