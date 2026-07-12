from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.database.session import get_db
from app.modules.activity.schemas import ActivityLogRead
from app.modules.activity.service import ActivityService
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/notifications", response_model=list[ActivityLogRead])
async def notifications(
    category: str | None = Query(
        default=None, description="e.g. alerts, approvals, bookings -- or any category in use"
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityLogRead]:
    service = ActivityService(session)
    await service.sync_due_notifications(current_user)
    rows = await service.feed(
        category=category,
        recipient_id=current_user.id,
        offset=offset,
        limit=limit,
    )
    return [ActivityLogRead.model_validate(row) for row in rows]


@router.post("/notifications/{log_id}/read", response_model=ActivityLogRead)
async def mark_notification_read(
    log_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActivityLogRead:
    row = await ActivityService(session).mark_read(log_id, recipient_id=current_user.id)
    if row is None:
        raise HTTPException(404, "Notification not found")
    return ActivityLogRead.model_validate(row)


@router.get(
    "/logs",
    response_model=list[ActivityLogRead],
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.ASSET_MANAGER))],
)
async def audit_logs(
    category: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> list[ActivityLogRead]:
    rows = await ActivityService(session).feed(
        category=category,
        audit_log_only=True,
        offset=offset,
        limit=limit,
    )
    return [ActivityLogRead.model_validate(row) for row in rows]
