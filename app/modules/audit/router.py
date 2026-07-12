from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.audit.schemas import (
    AuditCycleCreate,
    AuditCycleDetail,
    AuditCycleRead,
    AuditItemRead,
    AuditItemVerify,
    DiscrepancyReport,
    DiscrepancyResolution,
)
from app.modules.audit.service import AuditError, AuditPermissionError, AuditService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/cycles",
    response_model=list[AuditCycleRead],
    dependencies=[
        Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER, UserRole.DEPARTMENT_HEAD))
    ],
)
async def list_cycles(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditCycleRead]:
    """Cycles visible to the caller: all for Admin/Asset Manager, or scoped to the
    caller's department/assigned-auditor cycles for a Department Head."""
    rows = await AuditService(session).list_cycles(actor=current_user)
    return [AuditCycleRead.model_validate(row) for row in rows]


@router.post(
    "/cycles",
    response_model=AuditCycleDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def create_cycle(
    data: AuditCycleCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditCycleDetail:
    service = AuditService(session)
    try:
        cycle = await service.create_cycle(data, created_by=current_user.id)
    except AuditError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AuditCycleDetail.model_validate(cycle)


@router.get("/cycles/{cycle_id}", response_model=AuditCycleDetail)
async def get_cycle(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditCycleDetail:
    service = AuditService(session)
    cycle = await service.get_cycle(cycle_id)
    if cycle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit cycle not found")
    if not service.may_view_cycle(cycle, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot view this audit cycle")
    return AuditCycleDetail.model_validate(cycle)


@router.post("/items/{item_id}/verify", response_model=AuditItemRead)
async def verify_item(
    item_id: UUID,
    data: AuditItemVerify,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditItemRead:
    service = AuditService(session)
    try:
        item = await service.verify_item(item_id, data, actor=current_user)
    except AuditPermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except AuditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AuditItemRead.model_validate(item)


@router.post(
    "/items/{item_id}/approve-discrepancy",
    response_model=AuditItemRead,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def approve_discrepancy(
    item_id: UUID,
    data: DiscrepancyResolution,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditItemRead:
    try:
        item = await AuditService(session).approve_discrepancy(
            item_id, data, actor=current_user
        )
    except AuditError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AuditItemRead.model_validate(item)


@router.post(
    "/cycles/{cycle_id}/close",
    response_model=AuditCycleDetail,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def close_cycle(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditCycleDetail:
    service = AuditService(session)
    try:
        cycle = await service.close_cycle(cycle_id, actor_id=current_user.id)
    except AuditError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AuditCycleDetail.model_validate(cycle)


@router.get("/cycles/{cycle_id}/discrepancy-report", response_model=DiscrepancyReport)
async def discrepancy_report(
    cycle_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiscrepancyReport:
    service = AuditService(session)
    cycle = await service.get_cycle(cycle_id)
    if cycle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit cycle not found")
    if not service.may_view_cycle(cycle, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot view this audit cycle")
    return await service.discrepancy_report(cycle_id)
