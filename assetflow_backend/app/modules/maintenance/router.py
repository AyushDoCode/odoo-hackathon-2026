from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.maintenance.schemas import (
    MaintenanceRequestCreate,
    MaintenanceRequestRead,
    TechnicianAssign,
)
from app.modules.maintenance.service import MaintenanceError, MaintenanceService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

_ASSET_MANAGER_ONLY = [Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))]


@router.post("", response_model=MaintenanceRequestRead, status_code=status.HTTP_201_CREATED)
async def raise_request(
    data: MaintenanceRequestCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceRequestRead:
    service = MaintenanceService(session)
    request = await service.raise_request(data, created_by=current_user.id)
    return MaintenanceRequestRead.model_validate(request)


@router.get("/board", response_model=list[MaintenanceRequestRead])
async def board(
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[MaintenanceRequestRead]:
    service = MaintenanceService(session)
    rows = await service.board()
    return [MaintenanceRequestRead.model_validate(row) for row in rows]


@router.get("/asset/{asset_id}/history", response_model=list[MaintenanceRequestRead])
async def history(
    asset_id: UUID,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[MaintenanceRequestRead]:
    service = MaintenanceService(session)
    rows = await service.history_for_asset(asset_id)
    return [MaintenanceRequestRead.model_validate(row) for row in rows]


@router.post(
    "/{request_id}/approve", response_model=MaintenanceRequestRead, dependencies=_ASSET_MANAGER_ONLY
)
async def approve(
    request_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceRequestRead:
    service = MaintenanceService(session)
    try:
        request = await service.approve(request_id, approved_by=current_user.id)
    except MaintenanceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return MaintenanceRequestRead.model_validate(request)


@router.post(
    "/{request_id}/reject", response_model=MaintenanceRequestRead, dependencies=_ASSET_MANAGER_ONLY
)
async def reject(
    request_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceRequestRead:
    service = MaintenanceService(session)
    try:
        request = await service.reject(request_id, approved_by=current_user.id)
    except MaintenanceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return MaintenanceRequestRead.model_validate(request)


@router.post(
    "/{request_id}/assign-technician",
    response_model=MaintenanceRequestRead,
    dependencies=_ASSET_MANAGER_ONLY,
)
async def assign_technician(
    request_id: UUID,
    data: TechnicianAssign,
    session: AsyncSession = Depends(get_db),
) -> MaintenanceRequestRead:
    service = MaintenanceService(session)
    try:
        request = await service.assign_technician(request_id, data.technician_id)
    except MaintenanceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return MaintenanceRequestRead.model_validate(request)


@router.post("/{request_id}/start-progress", response_model=MaintenanceRequestRead)
async def start_progress(
    request_id: UUID,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> MaintenanceRequestRead:
    service = MaintenanceService(session)
    try:
        request = await service.start_progress(request_id)
    except MaintenanceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return MaintenanceRequestRead.model_validate(request)


@router.post("/{request_id}/resolve", response_model=MaintenanceRequestRead)
async def resolve(
    request_id: UUID,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> MaintenanceRequestRead:
    service = MaintenanceService(session)
    try:
        request = await service.resolve(request_id)
    except MaintenanceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return MaintenanceRequestRead.model_validate(request)
