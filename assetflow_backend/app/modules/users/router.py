from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserRead, UserUpdate
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["organization"])


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_role(UserRole.ADMIN))])
async def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    rows = await UserService(session).list_users(offset=offset, limit=limit)
    return [UserRead.model_validate(row) for row in rows]


@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(require_role(UserRole.ADMIN))])
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    service = UserService(session)
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == current_user.id and data.is_active is False:
        raise HTTPException(409, "Admin cannot deactivate their own account")
    user = await service.update_user(user, data)
    return UserRead.model_validate(user)
