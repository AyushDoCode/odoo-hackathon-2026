from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.allocations.schemas import (
    AllocationCreate,
    AllocationRead,
    ReturnRequest,
    TransferRequestCreate,
)
from app.modules.allocations.service import (
    AllocationError,
    AllocationPermissionError,
    AllocationService,
)
from app.modules.assets.service import AssetService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/allocations", tags=["allocations"])


@router.post(
    "",
    response_model=AllocationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def allocate_asset(
    data: AllocationCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllocationRead:
    service = AllocationService(session)
    try:
        allocation = await service.allocate(data, created_by=current_user.id)
    except AllocationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AllocationRead.model_validate(allocation)


@router.post("/{asset_id}/transfer-request", response_model=AllocationRead)
async def request_transfer(
    asset_id: UUID,
    data: TransferRequestCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllocationRead:
    service = AllocationService(session)
    try:
        allocation = await service.request_transfer(asset_id, data, actor=current_user)
    except AllocationPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except AllocationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AllocationRead.model_validate(allocation)


@router.post(
    "/{allocation_id}/approve-transfer",
    response_model=AllocationRead,
    dependencies=[
        Depends(
            require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER, UserRole.DEPARTMENT_HEAD)
        )
    ],
)
async def approve_transfer(
    allocation_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllocationRead:
    service = AllocationService(session)
    try:
        allocation = await service.approve_transfer(allocation_id, actor=current_user)
    except AllocationPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except AllocationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AllocationRead.model_validate(allocation)


@router.post("/{asset_id}/return-request", response_model=AllocationRead)
async def request_return(
    asset_id: UUID,
    data: ReturnRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllocationRead:
    service = AllocationService(session)
    try:
        allocation = await service.request_return(
            asset_id, data.return_condition, actor=current_user
        )
    except AllocationPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except AllocationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AllocationRead.model_validate(allocation)


@router.post(
    "/{allocation_id}/approve-return",
    response_model=AllocationRead,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def approve_return(
    allocation_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllocationRead:
    try:
        allocation = await AllocationService(session).approve_return(
            allocation_id, actor_id=current_user.id
        )
    except AllocationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AllocationRead.model_validate(allocation)


@router.get("/asset/{asset_id}/history", response_model=list[AllocationRead])
async def allocation_history(
    asset_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AllocationRead]:
    if not await AssetService(session).may_view(asset_id, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot view this asset history")
    service = AllocationService(session)
    rows = await service.history(asset_id)
    return [AllocationRead.model_validate(row) for row in rows]
