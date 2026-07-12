from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.modules.activity.service import record as record_activity
from app.database.session import get_db
from app.modules.users.models import User, UserRole
from app.modules.users.schemas import UserRead, UserUpdate
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["organization"])


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[
        Depends(
            require_role(
                UserRole.ADMIN,
                UserRole.ASSET_MANAGER,
                UserRole.DEPARTMENT_HEAD,
            )
        )
    ],
)
async def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserRead]:
    department_id = (
        current_user.department_id
        if current_user.role == UserRole.DEPARTMENT_HEAD
        else None
    )
    rows = await UserService(session).list_users(
        department_id=department_id, offset=offset, limit=limit
    )
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
    resulting_role = data.role if data.role is not None else user.role
    resulting_department = (
        data.department_id if "department_id" in data.model_fields_set else user.department_id
    )
    if resulting_role == UserRole.DEPARTMENT_HEAD and resulting_department is None:
        raise HTTPException(409, "Department Head must belong to a department")
    try:
        user = await service.update_user(user, data)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Email or department assignment conflicts with existing data") from exc
    await record_activity(
        session,
        actor_id=current_user.id,
        action_type="user.updated",
        category="organization",
        target_type="user",
        target_id=user.id,
        message=f"Employee {user.email} updated",
    )
    await session.commit()
    return UserRead.model_validate(user)
