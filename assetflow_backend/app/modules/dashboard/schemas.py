from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.modules.activity.schemas import ActivityLogRead


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets_available: int
    assets_allocated: int
    maintenance_today: int
    active_bookings: int
    pending_transfers: int
    upcoming_returns: int
    overdue_returns: int
    recent_activity: list[ActivityLogRead]
