from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.modules.activity.schemas import ActivityLogRead
from app.modules.activity.service import ActivityService
from app.modules.users.models import User

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityLogRead])
async def feed(
    category: str | None = Query(
        default=None, description="e.g. alerts, approvals, bookings -- or any category in use"
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[ActivityLogRead]:
    service = ActivityService(session)
    rows = await service.feed(category=category, offset=offset, limit=limit)
    return [ActivityLogRead.model_validate(row) for row in rows]
