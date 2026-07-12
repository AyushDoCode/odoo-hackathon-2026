from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.assets.models import AssetStatus
from app.modules.assets.schemas import AssetCreate, AssetRead, AssetUpdate
from app.modules.assets.service import AssetConflictError, AssetService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post(
    "",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def register_asset(
    data: AssetCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetRead:
    service = AssetService(session)
    try:
        asset = await service.create_asset(data, created_by=current_user.id)
    except AssetConflictError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AssetRead.model_validate(asset)


@router.get("", response_model=list[AssetRead])
async def list_assets(
    q: str | None = Query(default=None, description="Search by tag, serial number, or QR code"),
    category_id: UUID | None = None,
    status_filter: AssetStatus | None = Query(default=None, alias="status"),
    department_id: UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[AssetRead]:
    service = AssetService(session)
    assets = await service.search_assets(
        query=q,
        category_id=category_id,
        status=status_filter,
        department_id=department_id,
        offset=offset,
        limit=limit,
    )
    return [AssetRead.model_validate(asset) for asset in assets]


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: UUID,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AssetRead:
    service = AssetService(session)
    asset = await service.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return AssetRead.model_validate(asset)


@router.patch(
    "/{asset_id}",
    response_model=AssetRead,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def update_asset(
    asset_id: UUID,
    data: AssetUpdate,
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    service = AssetService(session)
    asset = await service.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    asset = await service.update_asset(asset, data)
    return AssetRead.model_validate(asset)


@router.post(
    "/{asset_id}/status",
    response_model=AssetRead,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def set_asset_status(
    asset_id: UUID,
    new_status: AssetStatus = Body(embed=True, alias="status"),
    session: AsyncSession = Depends(get_db),
) -> AssetRead:
    """Manually set Available/Reserved/Retired/Disposed. Allocated/Maintenance/Lost are
    set only by their owning workflow (allocations/maintenance/audit) and are rejected
    here.
    """
    service = AssetService(session)
    try:
        asset = await service.set_manual_status(asset_id, new_status)
    except AssetConflictError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    asset = await service.get_asset(asset_id)
    return AssetRead.model_validate(asset)
