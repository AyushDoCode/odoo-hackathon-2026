from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activity.service import notify, record as record_activity
from app.modules.assets.repository import AssetRepository
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.bookings.repository import BookingRepository
from app.modules.bookings.schemas import BookingCreate
from app.modules.users.models import User, UserRole


class BookingError(ValueError):
    """Raised when a booking can't be created (slot unavailable, resource not bookable)."""


class BookingPermissionError(PermissionError):
    """Raised when a caller tries to change another user's booking."""


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BookingRepository(session)
        self.assets = AssetRepository(session)

    async def create_booking(self, data: BookingCreate, *, actor: User) -> Booking:
        """Race-safe: locks the resource (asset) row first, serializing every booking
        attempt for that resource through a single row lock -- a plain SELECT ... FOR
        UPDATE against the (not-yet-existing) overlapping booking rows can't prevent a
        phantom-insert race, since a SELECT that matches zero rows locks nothing. Locking
        the resource row instead means a concurrent request for the same resource always
        blocks until this transaction commits, then re-checks overlap against the fresh
        committed state.
        """
        start_time = self._as_utc(data.start_time)
        end_time = self._as_utc(data.end_time)

        resource = await self.assets.get_by_id_for_update(data.resource_id)
        if resource is None:
            await self.session.rollback()
            raise BookingError("Resource not found")
        if not resource.is_bookable:
            await self.session.rollback()
            raise BookingError("This asset is not marked as a shared/bookable resource")
        if (
            data.department_id is not None
            and actor.role not in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
            and actor.department_id != data.department_id
        ):
            await self.session.rollback()
            raise BookingPermissionError("You may only book on behalf of your own department")

        overlaps = await self.repository.overlapping(data.resource_id, start_time, end_time)
        if overlaps:
            await self.session.rollback()
            raise BookingError("Slot unavailable: overlaps an existing booking")

        booking = Booking(
            resource_id=data.resource_id,
            user_id=actor.id,
            department_id=data.department_id,
            start_time=start_time,
            end_time=end_time,
            purpose=data.purpose,
            status=BookingStatus.BOOKED,
            created_by=actor.id,
        )
        self.repository.add(booking)
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="booking.confirmed",
            category="bookings",
            target_type="booking",
            target_id=None,
            message=f"Resource {data.resource_id} booked {data.start_time}-{data.end_time}",
        )
        await notify(
            self.session,
            recipient_id=actor.id,
            actor_id=actor.id,
            action_type="booking.confirmed",
            category="bookings",
            target_type="booking",
            target_id=booking.id,
            message=f"Booking confirmed for resource {data.resource_id}",
        )
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    @staticmethod
    def _may_manage(booking: Booking, actor: User) -> bool:
        return (
            actor.id == booking.user_id
            or actor.role in {UserRole.ADMIN, UserRole.ASSET_MANAGER}
            or (
                actor.role == UserRole.DEPARTMENT_HEAD
                and actor.department_id is not None
                and actor.department_id == booking.department_id
            )
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise BookingError("Booking times must include a timezone")
        return value.astimezone(UTC)

    async def cancel_booking(self, booking_id: UUID, *, actor: User) -> Booking:
        booking = await self.repository.get_by_id(booking_id)
        if booking is None:
            raise BookingError("Booking not found")
        if not self._may_manage(booking, actor):
            raise BookingPermissionError("You may only cancel your own or your department's booking")
        if booking.status == BookingStatus.CANCELLED:
            raise BookingError("Booking is already cancelled")
        booking_end = booking.end_time
        if booking_end.tzinfo is None:
            booking_end = booking_end.replace(tzinfo=UTC)
        else:
            booking_end = booking_end.astimezone(UTC)
        if booking_end <= datetime.now(UTC):
            raise BookingError("Completed bookings cannot be cancelled")
        booking.status = BookingStatus.CANCELLED
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="booking.cancelled",
            category="bookings",
            target_type="booking",
            target_id=booking.id,
            message=f"Booking {booking.id} cancelled",
        )
        await notify(
            self.session,
            recipient_id=booking.user_id,
            actor_id=actor.id,
            action_type="booking.cancelled",
            category="bookings",
            target_type="booking",
            target_id=booking.id,
            message=f"Booking {booking.id} was cancelled",
        )
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def reschedule_booking(
        self, booking_id: UUID, new_start: datetime, new_end: datetime, *, actor: User
    ) -> Booking:
        booking = await self.repository.get_by_id(booking_id)
        if booking is None:
            raise BookingError("Booking not found")
        if not self._may_manage(booking, actor):
            raise BookingPermissionError("You may only reschedule your own or your department's booking")
        if booking.status == BookingStatus.CANCELLED:
            raise BookingError("Cancelled bookings cannot be rescheduled")
        new_start = self._as_utc(new_start)
        new_end = self._as_utc(new_end)
        if new_end <= new_start:
            raise BookingError("end_time must be after start_time")
        if new_start <= datetime.now(UTC):
            raise BookingError("start_time must be in the future")

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
        await record_activity(
            self.session,
            actor_id=actor.id,
            action_type="booking.rescheduled",
            category="bookings",
            target_type="booking",
            target_id=booking.id,
            message=f"Booking {booking.id} rescheduled",
        )
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def for_resource(self, resource_id: UUID) -> list[Booking]:
        return await self.repository.for_resource(resource_id)
