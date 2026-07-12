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


async def _validate_parent(
    session: AsyncSession, department_id: UUID, parent_department_id: UUID | None
) -> None:
    """Walks the proposed parent's ancestor chain to reject cycles beyond the
    immediate self-parent case (e.g. A -> B -> A, or longer chains)."""
    service = DepartmentService(session)
    current_id = parent_department_id
    while current_id is not None:
        if current_id == department_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Department hierarchy cannot contain a cycle"
            )
        parent = await service.get_department(current_id)
        current_id = parent.parent_department_id if parent is not None else None


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
    if "parent_department_id" in data.model_fields_set:
        await _validate_parent(session, department_id, data.parent_department_id)
    if "head_id" in data.model_fields_set:
        await _validate_head(session, data.head_id)
    if row.is_active and data.is_active is False:
        active_members = await UserRepository(session).count_active_in_department(department_id)
        if active_members > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Cannot deactivate: {active_members} active employee(s) still belong to this department",
            )
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
