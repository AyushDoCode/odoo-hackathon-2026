from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import record as record_activity
from app.modules.assets.repository import AssetRepository
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.bookings.repository import BookingRepository
from app.modules.bookings.schemas import BookingCreate


class BookingError(ValueError):
    """Raised when a booking can't be created (slot unavailable, resource not bookable)."""


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BookingRepository(session)
        self.assets = AssetRepository(session)

    async def create_booking(self, data: BookingCreate, *, created_by: UUID) -> Booking:
        """Race-safe: locks the resource (asset) row first, serializing every booking
        attempt for that resource through a single row lock -- a plain SELECT ... FOR
        UPDATE against the (not-yet-existing) overlapping booking rows can't prevent a
        phantom-insert race, since a SELECT that matches zero rows locks nothing. Locking
        the resource row instead means a concurrent request for the same resource always
        blocks until this transaction commits, then re-checks overlap against the fresh
        committed state.
        """
        resource = await self.assets.get_by_id_for_update(data.resource_id)
        if resource is None:
            await self.session.rollback()
            raise BookingError("Resource not found")
        if not resource.is_bookable:
            await self.session.rollback()
            raise BookingError("This asset is not marked as a shared/bookable resource")

        overlaps = await self.repository.overlapping(
            data.resource_id, data.start_time, data.end_time
        )
        if overlaps:
            await self.session.rollback()
            raise BookingError("Slot unavailable: overlaps an existing booking")

        booking = Booking(
            resource_id=data.resource_id,
            user_id=created_by,
            department_id=data.department_id,
            start_time=data.start_time,
            end_time=data.end_time,
            purpose=data.purpose,
            status=BookingStatus.BOOKED,
            created_by=created_by,
        )
        self.repository.add(booking)
        await record_activity(
            self.session,
            actor_id=created_by,
            action_type="booking.confirmed",
            category="bookings",
            target_type="booking",
            target_id=None,
            message=f"Resource {data.resource_id} booked {data.start_time}-{data.end_time}",
        )
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def cancel_booking(self, booking_id: UUID) -> Booking:
        booking = await self.repository.get_by_id(booking_id)
        if booking is None:
            raise BookingError("Booking not found")
        booking.status = BookingStatus.CANCELLED
        await record_activity(
            self.session,
            actor_id=booking.user_id,
            action_type="booking.cancelled",
            category="bookings",
            target_type="booking",
            target_id=booking.id,
            message=f"Booking {booking.id} cancelled",
        )
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def reschedule_booking(
        self, booking_id: UUID, new_start: datetime, new_end: datetime
    ) -> Booking:
        booking = await self.repository.get_by_id(booking_id)
        if booking is None:
            raise BookingError("Booking not found")

        resource = await self.assets.get_by_id_for_update(booking.resource_id)
        if resource is None:
            await self.session.rollback()
            raise BookingError("Resource not found")

        overlaps = [
            b
            for b in await self.repository.overlapping(booking.resource_id, new_start, new_end)
            if b.id != booking.id
        ]
        if overlaps:
            await self.session.rollback()
            raise BookingError("Slot unavailable: overlaps an existing booking")

        booking.start_time = new_start
        booking.end_time = new_end
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def for_resource(self, resource_id: UUID) -> list[Booking]:
        return await self.repository.for_resource(resource_id)
