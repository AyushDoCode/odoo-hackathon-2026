from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.modules.activity.service import record as record_activity
from app.database.session import get_db
from app.modules.departments.schemas import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.modules.departments.service import DepartmentService
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

router = APIRouter(prefix="/departments", tags=["organization"])
_ADMIN_ONLY = [Depends(require_role(UserRole.ADMIN))]


async def _validate_head(session: AsyncSession, head_id: UUID | None) -> None:
    if head_id is None:
        return
    head = await UserRepository(session).get_by_id(head_id)
    if head is None or not head.is_active or head.role != UserRole.DEPARTMENT_HEAD:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Department head must be an active user with the Department Head role",
        )


@router.get("", response_model=list[DepartmentRead])
async def list_departments(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[DepartmentRead]:
    rows = await DepartmentService(session).list_departments(offset=offset, limit=limit)
    return [DepartmentRead.model_validate(row) for row in rows]


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED, dependencies=_ADMIN_ONLY)
async def create_department(
    data: DepartmentCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentRead:
    await _validate_head(session, data.head_id)
    try:
        row = await DepartmentService(session).create_department(data)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Department name or relationship is invalid") from exc
    await record_activity(
        session,
        actor_id=current_user.id,
        action_type="department.created",
        category="organization",
        target_type="department",
        target_id=row.id,
        message=f"Department {row.name} created",
    )
    await session.commit()
    return DepartmentRead.model_validate(row)


@router.patch("/{department_id}", response_model=DepartmentRead, dependencies=_ADMIN_ONLY)
async def update_department(
    department_id: UUID,
    data: DepartmentUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentRead:
    service = DepartmentService(session)
    row = await service.get_department(department_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    if data.parent_department_id == department_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Department cannot be its own parent")
    if "head_id" in data.model_fields_set:
        await _validate_head(session, data.head_id)
    try:
        row = await service.update_department(row, data)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Department name or relationship is invalid") from exc
    await record_activity(
        session,
        actor_id=current_user.id,
        action_type="department.updated",
        category="organization",
        target_type="department",
        target_id=row.id,
        message=f"Department {row.name} updated",
    )
    await session.commit()
    return DepartmentRead.model_validate(row)
