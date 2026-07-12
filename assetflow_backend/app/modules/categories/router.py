from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.modules.activity.service import record as record_activity
from app.database.session import get_db
from app.modules.categories.schemas import AssetCategoryCreate, AssetCategoryRead, AssetCategoryUpdate
from app.modules.categories.service import AssetCategoryService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/categories", tags=["organization"])
_ADMIN_ONLY = [Depends(require_role(UserRole.ADMIN))]


@router.get("", response_model=list[AssetCategoryRead])
async def list_categories(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[AssetCategoryRead]:
    rows = await AssetCategoryService(session).list_categories(offset=offset, limit=limit)
    return [AssetCategoryRead.model_validate(row) for row in rows]


@router.post("", response_model=AssetCategoryRead, status_code=status.HTTP_201_CREATED, dependencies=_ADMIN_ONLY)
async def create_category(
    data: AssetCategoryCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetCategoryRead:
    try:
        row = await AssetCategoryService(session).create_category(data)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Category name already exists") from exc
    await record_activity(
        session,
        actor_id=current_user.id,
        action_type="category.created",
        category="organization",
        target_type="asset_category",
        target_id=row.id,
        message=f"Category {row.name} created",
    )
    await session.commit()
    return AssetCategoryRead.model_validate(row)


@router.patch("/{category_id}", response_model=AssetCategoryRead, dependencies=_ADMIN_ONLY)
async def update_category(
    category_id: UUID,
    data: AssetCategoryUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetCategoryRead:
    service = AssetCategoryService(session)
    row = await service.get_category(category_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    try:
        row = await service.update_category(row, data)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Category name already exists") from exc
    await record_activity(
        session,
        actor_id=current_user.id,
        action_type="category.updated",
        category="organization",
        target_type="asset_category",
        target_id=row.id,
        message=f"Category {row.name} updated",
    )
    await session.commit()
    return AssetCategoryRead.model_validate(row)
