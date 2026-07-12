from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import Booking, BookingStatus


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, booking_id: UUID) -> Booking | None:
        return await self.session.get(Booking, booking_id)

    async def overlapping(
        self, resource_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[Booking]:
        """Existing BOOKED rows for this resource that overlap [start_time, end_time).
        Caller must already hold a lock serializing writers for this resource (the
        resource/asset row) -- this alone can't prevent phantom-insert races because a
        SELECT that returns zero rows locks nothing.
        """
        statement = select(Booking).where(
            Booking.resource_id == resource_id,
            Booking.status == BookingStatus.BOOKED,
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def for_resource(self, resource_id: UUID) -> list[Booking]:
        statement = (
            select(Booking)
            .where(Booking.resource_id == resource_id)
            .order_by(Booking.start_time)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    def add(self, booking: Booking) -> None:
        self.session.add(booking)
