from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.modules.bookings.schemas import BookingCreate, BookingRead
from app.modules.bookings.service import BookingError, BookingPermissionError, BookingService
from app.modules.users.models import User

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    service = BookingService(session)
    try:
        booking = await service.create_booking(data, actor=current_user)
    except BookingPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except BookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return BookingRead.model_validate(booking)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
async def cancel_booking(
    booking_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    service = BookingService(session)
    try:
        booking = await service.cancel_booking(booking_id, actor=current_user)
    except BookingPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except BookingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return BookingRead.model_validate(booking)


@router.post("/{booking_id}/reschedule", response_model=BookingRead)
async def reschedule_booking(
    booking_id: UUID,
    start_time: datetime = Body(embed=True),
    end_time: datetime = Body(embed=True),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    service = BookingService(session)
    try:
        booking = await service.reschedule_booking(
            booking_id, start_time, end_time, actor=current_user
        )
    except BookingPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except BookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return BookingRead.model_validate(booking)


@router.get("/resource/{resource_id}", response_model=list[BookingRead])
async def bookings_for_resource(
    resource_id: UUID,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[BookingRead]:
    service = BookingService(session)
    rows = await service.for_resource(resource_id)
    return [BookingRead.model_validate(row) for row in rows]
